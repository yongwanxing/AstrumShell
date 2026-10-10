"""插件加载 Pro - 核心管理器"""
import sys
import json
import importlib.util
from pathlib import Path
from typing import Any, Optional

from oss.plugin.types import Plugin
from .config import ProConfig
from .registry import CapabilityRegistry
from .proxy import PluginProxy, PermissionError
from ..models.plugin_info import PluginInfo
from ..circuit.breaker import CircuitBreaker
from ..retry.handler import RetryHandler
from ..fallback.handler import FallbackHandler
from ..recovery.health import HealthChecker
from ..recovery.auto_fix import AutoRecovery
from ..isolation.timeout import TimeoutController, TimeoutError
from ..utils.logger import ProLogger
from oss.plugin.capabilities import scan_capabilities


class ProPluginManager:
    """Pro 插件管理器"""

    def __init__(self, config: ProConfig):
        self.config = config
        self.plugins: dict[str, dict[str, Any]] = {}
        self.capability_registry = CapabilityRegistry()
        self._breakers: dict[str, CircuitBreaker] = {}
        self._health_checker = HealthChecker(
            config.health_check.interval,
            config.health_check.timeout,
            config.health_check.max_failures
        )
        self._auto_recovery = AutoRecovery(
            config.auto_recovery.max_attempts,
            config.auto_recovery.delay
        )

    def load_all(self, store_dir: str = "store"):
        """加载所有插件"""
        ProLogger.info("loader", "开始扫描插件...")

        self._load_from_dir(Path(store_dir))

        ProLogger.info("loader", f"共加载 {len(self.plugins)} 个插件")

    def _load_from_dir(self, store_dir: Path):
        """从目录加载插件"""
        if not store_dir.exists():
            return

        for author_dir in store_dir.iterdir():
            if not author_dir.is_dir():
                continue

            for plugin_dir in author_dir.iterdir():
                if not plugin_dir.is_dir():
                    continue

                main_file = plugin_dir / "main.py"
                if not main_file.exists():
                    continue

                self._load_single_plugin(plugin_dir)

    def _load_single_plugin(self, plugin_dir: Path) -> Optional[Any]:
        """加载单个插件"""
        main_file = plugin_dir / "main.py"
        manifest_file = plugin_dir / "manifest.json"

        try:
            manifest = {}
            if manifest_file.exists():
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

            spec = importlib.util.spec_from_file_location(
                f"pro_plugin.{plugin_dir.name}", str(main_file)
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            if not hasattr(module, "New"):
                return None

            instance = module.New()

            plugin_name = plugin_dir.name.rstrip("}")
            permissions = manifest.get("permissions", [])

            if permissions:
                instance = PluginProxy(
                    plugin_name, instance, permissions, self.plugins
                )

            info = PluginInfo()
            meta = manifest.get("metadata", {})
            info.name = meta.get("name", plugin_name)
            info.version = meta.get("version", "1.0.0")
            info.author = meta.get("author", "")
            info.description = meta.get("description", "")
            info.dependencies = manifest.get("dependencies", [])
            info.capabilities = scan_capabilities(plugin_dir)

            for cap in info.capabilities:
                self.capability_registry.register_provider(
                    cap, plugin_name, instance
                )

            self._breakers[plugin_name] = CircuitBreaker(
                self.config.circuit_breaker.failure_threshold,
                self.config.circuit_breaker.recovery_timeout,
                self.config.circuit_breaker.half_open_requests
            )

            self.plugins[plugin_name] = {
                "instance": instance,
                "module": module,
                "info": info,
                "permissions": permissions,
                "dir": plugin_dir
            }

            ProLogger.info("loader", f"已加载: {plugin_name} v{info.version}")
            return instance

        except Exception as e:
            ProLogger.error("loader", f"加载失败 {plugin_dir.name}: {type(e).__name__}: {e}")
            return None

    def init_and_start_all(self):
        """初始化并启动所有插件"""
        ProLogger.info("manager", "开始初始化所有插件...")

        self._inject_dependencies()
        ordered = self._get_ordered_plugins()

        for name in ordered:
            self._safe_init(name)

        ProLogger.info("manager", "开始启动所有插件...")
        for name in ordered:
            self._safe_start(name)

        self._health_checker.start(
            on_failure_callback=self._on_plugin_failure
        )

    def _safe_init(self, name: str):
        """安全初始化插件"""
        info = self.plugins[name]
        instance = info["instance"]
        breaker = self._breakers[name]

        try:
            breaker.call(instance.init)
            info["info"].status = "initialized"
            ProLogger.info("manager", f"已初始化: {name}")
        except Exception as e:
            ProLogger.error("manager", f"初始化失败 {name}: {type(e).__name__}: {e}")
            info["info"].status = "error"
            info["info"].error_count += 1
            info["info"].last_error = str(e)

    def _safe_start(self, name: str):
        """安全启动插件"""
        info = self.plugins[name]
        instance = info["instance"]
        breaker = self._breakers[name]

        try:
            breaker.call(instance.start)
            info["info"].status = "running"
            self._health_checker.add_plugin(name, instance)
            ProLogger.info("manager", f"已启动: {name}")
        except Exception as e:
            ProLogger.error("manager", f"启动失败 {name}: {type(e).__name__}: {e}")
            info["info"].status = "error"
            info["info"].error_count += 1
            info["info"].last_error = str(e)

    def stop_all(self):
        """停止所有插件"""
        self._health_checker.stop()

        for name in reversed(list(self.plugins.keys())):
            self._safe_stop(name)

    def _safe_stop(self, name: str):
        """安全停止插件"""
        info = self.plugins[name]
        instance = info["instance"]

        try:
            instance.stop()
            info["info"].status = "stopped"
            ProLogger.info("manager", f"已停止: {name}")
        except Exception as e:
            ProLogger.warn("manager", f"停止异常 {name}: {type(e).__name__}: {e}")

    def _on_plugin_failure(self, name: str):
        """插件失败回调"""
        ProLogger.error("recovery", f"插件 {name} 健康检查失败")

        if not self.config.auto_recovery.enabled:
            return

        info = self.plugins.get(name)
        if not info:
            return

        plugin_dir = info.get("dir")
        module = info.get("module")
        instance = info.get("instance")

        if plugin_dir:
            result = self._auto_recovery.attempt_recovery(
                name, plugin_dir, module, instance
            )
            if result:
                info["instance"] = result
                info["info"].status = "running"
                self._health_checker.reset_failure_count(name)

    def _inject_dependencies(self):
        """注入依赖"""
        name_map = {}
        for name in self.plugins:
            clean = name.rstrip("}")
            name_map[clean] = name
            name_map[clean + "}"] = name

        for name, info in self.plugins.items():
            deps = info["info"].dependencies
            if not deps:
                continue

            for dep_name in deps:
                actual_dep = name_map.get(dep_name) or name_map.get(dep_name + "}")
                if actual_dep and actual_dep in self.plugins:
                    dep_instance = self.plugins[actual_dep]["instance"]
                    setter = f"set_{dep_name.replace('-', '_')}"

                    if hasattr(info["instance"], setter):
                        try:
                            getattr(info["instance"], setter)(dep_instance)
                            ProLogger.info("inject", f"{name} <- {actual_dep}")
                        except Exception as e:
                            ProLogger.error("inject", f"注入失败 {name}.{setter}: {type(e).__name__}: {e}")

    def _get_ordered_plugins(self) -> list[str]:
        """获取插件顺序"""
        ordered = []
        visited = set()

        def visit(name):
            if name in visited:
                return
            visited.add(name)

            info = self.plugins.get(name)
            if not info:
                return

            for dep in info["info"].dependencies:
                clean_dep = dep.rstrip("}")
                if clean_dep in self.plugins:
                    visit(clean_dep)

            ordered.append(name)

        for name in self.plugins:
            visit(name)

        return ordered
