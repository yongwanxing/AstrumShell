"""插件加载增强器"""
from ..circuit.breaker import CircuitBreaker
from ..recovery.health import HealthChecker
from ..recovery.auto_fix import AutoRecovery
from ..utils.logger import ProLogger
from .config import ProConfig


class PluginLoaderEnhancer:
    """插件加载增强器 - 为现有 plugin-loader 提供高级机制"""

    def __init__(self, plugin_manager, config: ProConfig):
        self.pm = plugin_manager
        self.config = config
        self._breakers = {}
        self._health_checker = None
        self._auto_recovery = AutoRecovery(
            config.auto_recovery.max_attempts,
            config.auto_recovery.delay
        )
        self._enhanced = False

    def enhance(self):
        """增强 plugin-loader"""
        if self._enhanced:
            return

        ProLogger.info("enhancer", "开始增强 plugin-loader...")

        # 1. 为所有插件创建熔断器
        self._setup_circuit_breakers()

        # 2. 包装启动方法（带重试和容错）
        self._wrap_start_methods()

        # 3. 启动健康检查
        self._start_health_check()

        self._enhanced = True
        ProLogger.info("enhancer", "增强完成，共增强 {} 个插件".format(
            len(self.pm.plugins)
        ))

    def _setup_circuit_breakers(self):
        """为所有插件创建熔断器"""
        for name, info in self.pm.plugins.items():
            self._breakers[name] = CircuitBreaker(
                self.config.circuit_breaker.failure_threshold,
                self.config.circuit_breaker.recovery_timeout,
                self.config.circuit_breaker.half_open_requests
            )
            ProLogger.debug("enhancer", f"为 {name} 创建熔断器")

    def _wrap_start_methods(self):
        """包装启动方法"""
        original_start_all = getattr(self.pm, 'start_all', None)
        if original_start_all:
            def wrapped_start_all():
                self._safe_start_all()

            self.pm.start_all = wrapped_start_all
            ProLogger.info("enhancer", "已包装 start_all 方法")

        original_init_and_start = getattr(
            self.pm, 'init_and_start_all', None
        )
        if original_init_and_start:
            def wrapped_init_and_start():
                self._safe_init_and_start_all()

            self.pm.init_and_start_all = wrapped_init_and_start
            ProLogger.info("enhancer", "已包装 init_and_start_all 方法")

    def _safe_init_and_start_all(self):
        """安全的初始化并启动"""
        ordered = self._get_ordered_plugins()

        # 安全初始化
        for name in ordered:
            self._safe_call(name, 'init', '初始化')

        # 安全启动
        for name in ordered:
            self._safe_call(name, 'start', '启动')

    def _safe_start_all(self):
        """安全启动所有"""
        for name in self.pm.plugins:
            self._safe_call(name, 'start', '启动')

    def _safe_call(self, name: str, method: str, action: str):
        """安全调用插件方法（带熔断和重试）"""
        info = self.pm.plugins.get(name)
        if not info:
            return

        instance = info.get("instance")
        if not instance or not hasattr(instance, method):
            return

        breaker = self._breakers.get(name)
        if not breaker:
            # 没有熔断器，直接调用
            try:
                getattr(instance, method)()
            except Exception as e:
                ProLogger.error("safe", f"{name} {action}失败: {type(e).__name__}: {e}")
                self._on_plugin_error(name, info, str(e))
            return

        # 有熔断器，包装调用
        def do_call():
            return getattr(instance, method)()

        try:
            breaker.call(do_call)
            info["info"].error_count = 0
            ProLogger.info("safe", f"{name} {action}成功")
        except Exception as e:
            ProLogger.error("safe", f"{name} {action}失败: {type(e).__name__}: {e}")
            self._on_plugin_error(name, info, str(e))

    def _on_plugin_error(self, name: str, info: dict, error: str):
        """插件错误处理"""
        info["info"].error_count += 1
        info["info"].last_error = error

        # 自动恢复
        if self.config.auto_recovery.enabled:
            plugin_dir = info.get("dir")
            module = info.get("module")

            if plugin_dir:
                result = self._auto_recovery.attempt_recovery(
                    name, plugin_dir, module, info.get("instance")
                )
                if result:
                    info["instance"] = result
                    info["info"].error_count = 0
                    ProLogger.info("recovery", f"{name} 自动恢复成功")

    def _start_health_check(self):
        """启动健康检查"""
        self._health_checker = HealthChecker(
            self.config.health_check.interval,
            self.config.health_check.timeout,
            self.config.health_check.max_failures
        )

        for name, info in self.pm.plugins.items():
            self._health_checker.add_plugin(name, info["instance"])

        self._health_checker.start(
            on_failure_callback=self._on_health_check_failure
        )
        ProLogger.info("enhancer", "健康检查已启动")

    def _on_health_check_failure(self, name: str):
        """健康检查失败回调"""
        ProLogger.error("health", f"插件 {name} 健康检查失败")

        info = self.pm.plugins.get(name)
        if not info:
            return

        plugin_dir = info.get("dir")
        module = info.get("module")

        if plugin_dir:
            result = self._auto_recovery.attempt_recovery(
                name, plugin_dir, module, info.get("instance")
            )
            if result:
                info["instance"] = result
                self._health_checker.reset_failure_count(name)
                ProLogger.info("recovery", f"{name} 健康恢复成功")

    def _get_ordered_plugins(self) -> list[str]:
        """获取按依赖排序的插件列表"""
        ordered = []
        visited = set()

        def visit(name):
            if name in visited:
                return
            visited.add(name)

            info = self.pm.plugins.get(name)
            if not info:
                return

            for dep in info["info"].dependencies:
                clean_dep = dep.rstrip("}")
                if clean_dep in self.pm.plugins:
                    visit(clean_dep)

            ordered.append(name)

        for name in self.pm.plugins:
            visit(name)

        return ordered

    def disable(self):
        """禁用增强器"""
        if self._health_checker:
            self._health_checker.stop()
        self._enhanced = False
        ProLogger.info("enhancer", "增强器已禁用")
