"""插件加载器插件 - 支持能力扫描和扩展 + PL 注入机制"""
import sys
import json
import re
import types
import traceback
import importlib.util
from pathlib import Path
from typing import Any, Optional, Callable

from oss.plugin.types import Plugin, register_plugin_type
from oss.plugin.capabilities import scan_capabilities


class Log:
    """智能彩色日志"""
    _TTY = sys.stdout.isatty()
    _C = {"reset": "\033[0m", "white": "\033[0;37m", "yellow": "\033[1;33m", "blue": "\033[1;34m", "red": "\033[1;31m"}

    @classmethod
    def c(cls, text: str, color: str) -> str:
        if not cls._TTY: return text
        return f"{cls._C.get(color, '')}{text}{cls._C['reset']}"

    @classmethod
    def info(cls, tag: str, msg: str): print(f"{cls.c(f'[{tag}]', 'white')} {cls.c(msg, 'white')}")
    @classmethod
    def warn(cls, tag: str, msg: str): print(f"{cls.c(f'[{tag}]', 'yellow')} {cls.c('⚠', 'yellow')} {cls.c(msg, 'yellow')}")
    @classmethod
    def tip(cls, tag: str, msg: str): print(f"{cls.c(f'[{tag}]', 'blue')} {cls.c('ℹ', 'blue')} {cls.c(msg, 'blue')}")
    @classmethod
    def error(cls, tag: str, msg: str): print(f"{cls.c(f'[{tag}]', 'red')} {cls.c('✗', 'red')} {cls.c(msg, 'red')}")
    @classmethod
    def ok(cls, tag: str, msg: str): print(f"{cls.c(f'[{tag}]', 'white')} {cls.c(msg, 'white')}")


class PluginInfo:
    """插件信息"""
    def __init__(self):
        self.name: str = ""
        self.version: str = ""
        self.author: str = ""
        self.description: str = ""
        self.readme: str = ""
        self.config: dict[str, Any] = {}
        self.extensions: dict[str, Any] = {}
        self.lifecycle: Any = None
        self.capabilities: set[str] = set()
        self.dependencies: list[str] = []
        self.pl_injected: bool = False


class PermissionError(Exception):
    """权限错误"""
    pass


class PluginProxy:
    """插件代理 - 防止越级访问"""
    def __init__(self, plugin_name: str, plugin_instance: Any, allowed_plugins: list[str], all_plugins: dict):
        self._plugin_name = plugin_name
        self._plugin_instance = plugin_instance
        self._allowed_plugins = set(allowed_plugins)
        self._all_plugins = all_plugins

    def get_plugin(self, name: str) -> Any:
        if name not in self._allowed_plugins and "*" not in self._allowed_plugins:
            raise PermissionError(f"插件 '{self._plugin_name}' 无权访问插件 '{name}'")
        if name not in self._all_plugins: return None
        return self._all_plugins[name]["instance"]

    def list_plugins(self) -> list[str]:
        if "*" in self._allowed_plugins: return list(self._all_plugins.keys())
        return [n for n in self._allowed_plugins if n in self._all_plugins]

    def get_capability(self, capability: str) -> Any: return None
    def __getattr__(self, name: str): return getattr(self._plugin_instance, name)


class CapabilityRegistry:
    """能力注册表"""
    def __init__(self, permission_check: bool = True):
        self.providers: dict = {}
        self.consumers: dict = {}
        self.permission_check = permission_check

    def register_provider(self, capability: str, plugin_name: str, instance: Any):
        self.providers[capability] = {"plugin": plugin_name, "instance": instance}
        if capability not in self.consumers: self.consumers[capability] = []

    def register_consumer(self, capability: str, plugin_name: str):
        if capability not in self.consumers: self.consumers[capability] = []
        if plugin_name not in self.consumers[capability]: self.consumers[capability].append(plugin_name)

    def get_provider(self, capability: str, requester: str = "", allowed_plugins: list = None) -> Optional[Any]:
        if capability not in self.providers: return None
        if self.permission_check and allowed_plugins is not None:
            pn = self.providers[capability]["plugin"]
            if pn != requester and pn not in allowed_plugins and "*" not in allowed_plugins:
                raise PermissionError(f"插件 '{requester}' 无权使用能力 '{capability}'")
        return self.providers[capability]["instance"]

    def has_capability(self, capability: str) -> bool: return capability in self.providers
    def get_consumers(self, capability: str) -> list: return self.consumers.get(capability, [])


class PLValidationError(Exception):
    """PL 校验错误"""
    pass


class PLInjector:
    """PL 注入管理器 - 带完整安全限制"""

    MAX_FUNCTIONS_PER_PLUGIN = 50
    MAX_REGISTRATIONS_PER_NAME = 10
    MAX_NAME_LENGTH = 128
    MAX_DESCRIPTION_LENGTH = 256

    _FUNCTION_NAME_RE = re.compile(r'^[a-zA-Z0-9_:/\-.]+$')
    _EVENT_NAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_.]+$')
    _ROUTE_PATH_RE = re.compile(r'^/[a-zA-Z0-9_\-/.]+$')
    _FORBIDDEN_ROUTE_PATTERNS = [r'\.\.', r'//', r'/\.', r'~', r'\%']

    def __init__(self, plugin_manager: 'PluginManager'):
        self._plugin_manager = plugin_manager
        self._injections: dict = {}
        self._injection_registry: dict = {}
        self._plugin_function_count: dict = {}

    def check_and_load_pl(self, plugin_dir: Path, plugin_name: str) -> bool:
        """检查并加载 PL 文件夹，返回 True 表示成功"""
        pl_dir = plugin_dir / "PL"
        if not pl_dir.exists() or not pl_dir.is_dir():
            Log.warn("plugin-loader", f"插件 '{plugin_name}' 声明了 pl_injection，但缺少 PL/ 文件夹，拒绝加载")
            return False

        pl_main = pl_dir / "main.py"
        if not pl_main.exists():
            Log.warn("plugin-loader", f"插件 '{plugin_name}' 的 PL/ 文件夹中缺少 main.py，拒绝加载")
            return False

        # 禁止危险文件类型
        forbidden_ext = {'.sh', '.bat', '.exe', '.dll', '.so', '.dylib', '.bin'}
        for f in pl_dir.rglob('*'):
            if f.suffix.lower() in forbidden_ext:
                Log.error("plugin-loader", f"插件 '{plugin_name}' 的 PL/ 文件夹包含危险文件: {f.name}，拒绝加载")
                return False

        try:
            # 受限沙箱
            safe_builtins = {
                'True': True, 'False': False, 'None': None,
                'dict': dict, 'list': list, 'str': str, 'int': int,
                'float': float, 'bool': bool, 'tuple': tuple, 'set': set,
                'len': len, 'range': range, 'enumerate': enumerate,
                'zip': zip, 'map': map, 'filter': filter,
                'sorted': sorted, 'reversed': reversed,
                'min': min, 'max': max, 'sum': sum, 'abs': abs,
                'round': round, 'isinstance': isinstance, 'issubclass': issubclass,
                'type': type, 'id': id, 'hash': hash, 'repr': repr,
                'print': print, 'object': object, 'property': property,
                'staticmethod': staticmethod, 'classmethod': classmethod,
                'super': super, 'iter': iter, 'next': next,
                'any': any, 'all': all, 'callable': callable,
                'hasattr': hasattr, 'getattr': getattr, 'setattr': setattr,
                'ValueError': ValueError, 'TypeError': TypeError,
                'KeyError': KeyError, 'IndexError': IndexError,
                'Exception': Exception, 'BaseException': BaseException,
            }
            safe_globals = {
                '__builtins__': safe_builtins,
                '__name__': f'plugin.{plugin_name}.PL',
                '__package__': f'plugin.{plugin_name}.PL',
                '__file__': str(pl_main),
            }

            with open(pl_main, 'r', encoding='utf-8') as f:
                source = f.read()

            # 静态源码安全检查
            self._static_source_check(source, str(pl_main))

            code = compile(source, str(pl_main), 'exec')
            exec(code, safe_globals)

            register_func = safe_globals.get('register')
            if register_func and callable(register_func):
                register_func(self)
                Log.ok("plugin-loader", f"插件 '{plugin_name}' PL 注入成功")
            else:
                Log.warn("plugin-loader", f"插件 '{plugin_name}' 的 PL/main.py 缺少 register() 函数，但仍允许加载")

            self._injections[plugin_name] = {"dir": str(pl_dir)}
            return True

        except PLValidationError as e:
            Log.error("plugin-loader", f"插件 '{plugin_name}' PL 安全检查失败: {e}")
            return False
        except SyntaxError as e:
            Log.error("plugin-loader", f"插件 '{plugin_name}' PL/main.py 语法错误: {e}")
            return False
        except FileNotFoundError as e:
            Log.error("plugin-loader", f"插件 '{plugin_name}' PL 文件不存在：{e}")
            return False
        except PermissionError as e:
            Log.error("plugin-loader", f"插件 '{plugin_name}' PL 文件权限错误：{e}")
            return False
        except Exception as e:
            Log.error("plugin-loader", f"加载插件 '{plugin_name}' 的 PL 失败：{type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _static_source_check(self, source: str, file_path: str):
        """静态源码安全检查 - 增强版，防止字符串拼接/编码绕过"""
        import base64
        
        # 首先检查是否有 base64 编码的恶意代码
        try:
            # 查找所有字符串字面量
            string_pattern = r'([A-Za-z0-9+/=]{20,})'
            for match in re.finditer(string_pattern, source):
                try:
                    decoded = base64.b64decode(match.group(1)).decode('utf-8', errors='ignore')
                    # 检查解码后的内容
                    for dangerous in ['import ', 'exec(', 'eval(', 'compile(', 'os.', 'sys.', 'subprocess']:
                        if dangerous in decoded:
                            raise PLValidationError(f"{file_path} - 检测到 base64 编码的恶意代码")
                except:
                    pass
        except:
            pass
        
        # 检查字符串拼接绕过 (如 'ex' + 'ec')
        concat_patterns = [
            r"""['"]ex['"]\s*\+\s*['"]ec['"]""",
            r"""['"]impor['"]\s*\+\s*['"]t['"]""",
            r"""['"]eva['"]\s*\+\s*['"]l['"]""",
            r"""['"]compil['"]\s*\+\s*['"]e['"]""",
        ]
        for pattern in concat_patterns:
            if re.search(pattern, source):
                raise PLValidationError(f"{file_path} - 检测到字符串拼接绕过尝试")
        
        forbidden = [
            (r'^\s*import\s+(os|sys|subprocess|shutil|socket|ctypes|cffi|multiprocessing|threading)', '禁止导入系统级模块'),
            (r'^\s*from\s+(os|sys|subprocess|shutil|socket|ctypes|cffi|multiprocessing|threading)\s+import', '禁止导入系统级模块'),
            (r'__import__\s*\(', '禁止使用 __import__'),
            (r'(?<![a-zA-Z_])exec\s*\(', '禁止使用 exec'),
            (r'(?<![a-zA-Z_])eval\s*\(', '禁止使用 eval'),
            (r'(?<![a-zA-Z_])compile\s*\(', '禁止使用 compile'),
            (r'(?<![a-zA-Z_])open\s*\(', '禁止直接操作文件'),
            (r'__builtins__', '禁止访问 __builtins__'),
            (r'getattr\s*\(\s*__builtins__', '禁止通过 getattr 访问 __builtins__'),
            (r'setattr\s*\(', '禁止使用 setattr'),
            (r'type\s*\(\s*\(\s*[\'"]', '禁止使用 type 动态创建类'),
        ]
        for line_num, line in enumerate(source.split('\n'), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'): continue
            for pattern, msg in forbidden:
                if re.search(pattern, stripped):
                    raise PLValidationError(f"{file_path}:{line_num} - {msg}: '{stripped}'")

    def _validate_function_name(self, name: str) -> bool:
        if not name or not isinstance(name, str): return False
        if len(name) > self.MAX_NAME_LENGTH: return False
        return bool(self._FUNCTION_NAME_RE.match(name))

    def _validate_route_path(self, path: str) -> bool:
        if not path or not isinstance(path, str): return False
        if len(path) > 256: return False
        if not self._ROUTE_PATH_RE.match(path): return False
        for p in self._FORBIDDEN_ROUTE_PATTERNS:
            if re.search(p, path): return False
        return True

    def _validate_event_name(self, event_name: str) -> bool:
        if not event_name or not isinstance(event_name, str): return False
        if len(event_name) > self.MAX_NAME_LENGTH: return False
        return bool(self._EVENT_NAME_RE.match(event_name))

    def _check_plugin_limit(self, plugin_name: str) -> bool:
        count = self._plugin_function_count.get(plugin_name, 0)
        if count >= self.MAX_FUNCTIONS_PER_PLUGIN:
            Log.warn("plugin-loader", f"插件 '{plugin_name}' 注册功能数已达上限 ({self.MAX_FUNCTIONS_PER_PLUGIN})")
            return False
        return True

    def _check_name_limit(self, name: str) -> bool:
        registrations = self._injection_registry.get(name, [])
        if len(registrations) >= self.MAX_REGISTRATIONS_PER_NAME:
            Log.warn("plugin-loader", f"功能名称 '{name}' 注册次数已达上限 ({self.MAX_REGISTRATIONS_PER_NAME})")
            return False
        return True

    def _wrap_function(self, func: Callable, plugin_name: str, name: str) -> Callable:
        """包装函数，异常安全"""
        def _safe_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                Log.error("plugin-loader", f"PL 注入功能 '{name}' (来自 {plugin_name}) 执行异常: {e}")
                return None
        return _safe_wrapper

    def _get_caller_plugin_name(self) -> Optional[str]:
        """通过栈帧回溯获取调用者插件名"""
        stack = traceback.extract_stack()
        for frame in stack:
            filename = frame.filename
            if '/PL/' in filename and 'main.py' in filename:
                parts = Path(filename).parts
                for i, part in enumerate(parts):
                    if part == 'PL':
                        return parts[i - 1] if i > 0 else None
        return None

    def register_function(self, name: str, func: Callable, description: str = ""):
        """注册注入功能 - 带参数校验和权限限制"""
        if not self._validate_function_name(name):
            Log.error("plugin-loader", f"PL 注入功能名称非法: '{name}'")
            return
        if not callable(func):
            Log.error("plugin-loader", f"PL 注入功能 '{name}' 不是可调用对象")
            return
        if description and len(description) > self.MAX_DESCRIPTION_LENGTH:
            description = description[:self.MAX_DESCRIPTION_LENGTH]

        plugin_name = self._get_caller_plugin_name() or "unknown"

        if not self._check_plugin_limit(plugin_name): return
        if not self._check_name_limit(name): return

        wrapped_func = self._wrap_function(func, plugin_name, name)

        if name not in self._injection_registry:
            self._injection_registry[name] = []
        self._injection_registry[name].append({
            "func": wrapped_func, "plugin": plugin_name, "description": description,
        })
        self._plugin_function_count[plugin_name] = self._plugin_function_count.get(plugin_name, 0) + 1
        Log.tip("plugin-loader", f"PL 注入功能已注册: '{name}' (来自 {plugin_name})")

    def register_route(self, method: str, path: str, handler: Callable):
        """注册 HTTP 路由 - 带路径安全校验"""
        valid_methods = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'}
        method_upper = method.upper()
        if method_upper not in valid_methods:
            Log.error("plugin-loader", f"PL 注入路由方法非法: '{method}'")
            return
        if not self._validate_route_path(path):
            Log.error("plugin-loader", f"PL 注入路由路径非法: '{path}'")
            return
        self.register_function(f"{method_upper}:{path}", handler, f"路由 {method_upper} {path}")

    def register_event_handler(self, event_name: str, handler: Callable):
        """注册事件处理器 - 带名称校验"""
        if not self._validate_event_name(event_name):
            Log.error("plugin-loader", f"PL 注入事件名称非法: '{event_name}'")
            return
        self.register_function(f"event:{event_name}", handler, f"事件 {event_name}")

    def get_injected_functions(self, name: str = None) -> list[Callable]:
        if name: return [e["func"] for e in self._injection_registry.get(name, [])]
        return [f for es in self._injection_registry.values() for f in [e["func"] for e in es]]

    def get_injection_info(self, plugin_name: str = None) -> dict:
        if plugin_name: return self._injections.get(plugin_name, {})
        return dict(self._injections)

    def has_injection(self, plugin_name: str) -> bool:
        return plugin_name in self._injections

    def get_registry_info(self) -> dict:
        info = {}
        for name, entries in self._injection_registry.items():
            info[name] = {
                "count": len(entries),
                "plugins": [e["plugin"] for e in entries],
                "descriptions": [e["description"] for e in entries],
            }
        return info


class PluginManager:
    """插件管理器"""

    def __init__(self, permission_check: bool = True):
        self.plugins: dict = {}
        self.lifecycle_plugin = None
        self._dependency_plugin = None
        self._signature_verifier = None
        self.capability_registry = CapabilityRegistry(permission_check=permission_check)
        self.permission_check = permission_check
        self.enforce_signature = True
        self.pl_injector = PLInjector(self)

    def set_signature_verifier(self, verifier): self._signature_verifier = verifier
    def set_lifecycle(self, lifecycle_plugin): self.lifecycle_plugin = lifecycle_plugin

    def _load_manifest(self, plugin_dir: Path) -> dict:
        mf = plugin_dir / "manifest.json"
        if not mf.exists(): return {}
        with open(mf, "r", encoding="utf-8") as f: return json.load(f)

    def _load_readme(self, plugin_dir: Path) -> str:
        rf = plugin_dir / "README.md"
        if not rf.exists(): return ""
        with open(rf, "r", encoding="utf-8") as f: return f.read()

    def _load_config(self, plugin_dir: Path) -> dict:
        """加载插件配置文件 - 使用 ast.literal_eval 安全解析"""
        import ast
        cf = plugin_dir / "config.py"
        if not cf.exists():
            return {}
        try:
            with open(cf, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            Log.warn("plugin-loader", f"配置文件不存在：{cf}")
            return {}
        except PermissionError as e:
            Log.error("plugin-loader", f"配置文件无权限读取：{cf} - {e}")
            return {}
        except UnicodeDecodeError as e:
            Log.error("plugin-loader", f"配置文件编码错误：{cf} - {e}")
            return {}
        
        # 严格检查：不允许任何代码执行
        for p in ['import ', 'from ', 'open(', 'exec(', 'eval(', 'compile(', 'os.', 'sys.', 'subprocess', 'lambda', 'def ', 'class ']:
            if p in content:
                Log.warn("plugin-loader", f"{cf} 包含危险代码：{p}")
                return {}
        
        # 尝试使用 ast.literal_eval 安全解析
        try:
            result = ast.literal_eval(content)
            if isinstance(result, dict):
                return {k: v for k, v in result.items() if not k.startswith("_")}
        except (ValueError, SyntaxError):
            pass
        
        # 如果失败，尝试提取简单的键值对
        config = {}
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)$', line)
            if match:
                key, value_str = match.groups()
                if key.startswith('_'):
                    continue
                try:
                    value = ast.literal_eval(value_str)
                    config[key] = value
                except (ValueError, SyntaxError):
                    Log.warn("plugin-loader", f"{cf} 跳过无效的值：{line}")
                    continue
        return config


    def _load_extensions(self, plugin_dir: Path) -> dict:
        """加载插件扩展配置 - 使用 ast.literal_eval 安全解析"""
        import ast
        ef = plugin_dir / "extensions.py"
        if not ef.exists():
            return {}
        try:
            with open(ef, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            Log.error("plugin-loader", f"扩展文件读取失败：{e}")
            return {}
        
        # 严格检查：不允许任何代码执行
        for p in ['import ', 'from ', 'open(', 'exec(', 'eval(', 'compile(', 'os.', 'sys.', 'subprocess', 'lambda', 'def ', 'class ']:
            if p in content:
                Log.warn("plugin-loader", f"{ef} 包含危险代码：{p}")
                return {}
        
        # 尝试使用 ast.literal_eval 安全解析
        try:
            result = ast.literal_eval(content)
            if isinstance(result, dict):
                return {k: v for k, v in result.items() if not k.startswith("_")}
        except (ValueError, SyntaxError):
            pass
        
        # 如果失败，尝试提取简单的键值对
        extensions = {}
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)$', line)
            if match:
                key, value_str = match.groups()
                if key.startswith('_'):
                    continue
                try:
                    value = ast.literal_eval(value_str)
                    extensions[key] = value
                except (ValueError, SyntaxError):
                    Log.warn("plugin-loader", f"{ef} 跳过无效的值：{line}")
                    continue
        return extensions


    def load(self, plugin_dir: Path, use_sandbox: bool = True) -> Optional[Any]:
        """加载单个插件"""
        main_file = plugin_dir / "main.py"
        if not main_file.exists(): return None

        manifest = self._load_manifest(plugin_dir)
        readme = self._load_readme(plugin_dir)
        config = self._load_config(plugin_dir)
        extensions = self._load_extensions(plugin_dir)
        capabilities = scan_capabilities(plugin_dir)
        plugin_name = plugin_dir.name.rstrip("}")

        # PL 注入检查
        pl_injection = manifest.get("config", {}).get("args", {}).get("pl_injection", False)
        if pl_injection:
            Log.tip("plugin-loader", f"插件 '{plugin_name}' 声明了 pl_injection，正在检查 PL/ 文件夹...")
            if not self.pl_injector.check_and_load_pl(plugin_dir, plugin_name):
                Log.error("plugin-loader", f"插件 '{plugin_name}' 因 PL 注入检查失败被拒绝加载")
                return None
            Log.ok("plugin-loader", f"插件 '{plugin_name}' PL 注入检查通过")

        permissions = manifest.get("permissions", [])

        # 不再使用沙箱，所有插件都直接加载（核心插件是可信的）
        # use_sandbox 参数保留但不再实际使用
        spec = importlib.util.spec_from_file_location(f"plugin.{plugin_name}", str(main_file))
        module = importlib.util.module_from_spec(spec)
        module.__package__ = f"plugin.{plugin_name}"
        module.__path__ = [str(plugin_dir)]
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        if not hasattr(module, "New"):
            return None
        instance = module.New()

        if self.permission_check and permissions:
            instance = PluginProxy(plugin_name, instance, permissions, self.plugins)

        info = PluginInfo()
        meta = manifest.get("metadata", {})
        info.name = meta.get("name", plugin_name)
        info.version = meta.get("version", "")
        info.author = meta.get("author", "")
        info.description = meta.get("description", "")
        info.readme = readme
        info.config = manifest.get("config", {}).get("args", config)
        info.extensions = extensions
        info.capabilities = capabilities
        info.dependencies = manifest.get("dependencies", [])
        info.pl_injected = pl_injection

        for cap in capabilities:
            self.capability_registry.register_provider(cap, plugin_name, instance)
        if self.lifecycle_plugin and plugin_name != "lifecycle":
            info.lifecycle = self.lifecycle_plugin.create(plugin_name)

        self.plugins[plugin_name] = {"instance": instance, "module": module, "info": info, "permissions": permissions}
        return instance

    def load_all(self, store_dir: str = "store"):
        if 'plugin' not in sys.modules:
            pkg = types.ModuleType('plugin')
            pkg.__path__ = []; pkg.__package__ = 'plugin'
            sys.modules['plugin'] = pkg
            Log.tip("plugin-loader", "已创建 plugin 命名空间包")

        if not self._check_any_plugins(store_dir):
            Log.warn("plugin-loader", "未检测到任何插件，自动引导安装...")
            self._bootstrap_installation()

        lifecycle_plugin = None
        lc_dir = Path(store_dir) / "@{AstrumShell}" / "lifecycle"
        if lc_dir.exists() and (lc_dir / "main.py").exists():
            try:
                inst = self.load(lc_dir)
                if inst: lifecycle_plugin = inst; self.plugins.pop("lifecycle", None)
            except Exception as e: Log.warn("plugin-loader", f"lifecycle 插件加载失败：{type(e).__name__}: {e}")

        dep_plugin = None
        dep_dir = Path(store_dir) / "@{AstrumShell}" / "dependency"
        if dep_dir.exists() and (dep_dir / "main.py").exists():
            try:
                inst = self.load(dep_dir)
                if inst: dep_plugin = inst; self._dependency_plugin = inst; self.plugins.pop("dependency", None)
            except Exception as e: Log.warn("plugin-loader", f"dependency 插件加载失败：{type(e).__name__}: {e}")

        sig_dir = Path(store_dir) / "@{AstrumShell}" / "signature-verifier"
        if sig_dir.exists() and (sig_dir / "main.py").exists():
            try:
                inst = self.load(sig_dir)
                if inst: self.set_signature_verifier(inst.verifier); Log.ok("plugin-loader", "签名验证服务已加载")
            except Exception as e: Log.warn("plugin-loader", f"signature-verifier 加载失败: {e}")

        if lifecycle_plugin: self.set_lifecycle(lifecycle_plugin)
        self._load_plugins_from_dir(Path(store_dir))
        if dep_plugin: self._sort_by_dependencies(dep_plugin)

    def _load_plugins_from_dir(self, store_dir: Path):
        if not store_dir.exists(): return
        core_plugins = {"webui", "dashboard", "pkg-manager"}
        skip = {"plugin-loader", "lifecycle", "dependency", "signature-verifier"}
        for ad in store_dir.iterdir():
            if ad.is_dir():
                for pd in ad.iterdir():
                    if pd.is_dir() and pd.name not in skip and (pd / "main.py").exists():
                        self.load(pd, use_sandbox=pd.name not in core_plugins)
        self._link_capabilities()

    def _check_any_plugins(self, store_dir: str) -> bool:
        sp = Path(store_dir)
        if sp.exists():
            for ad in sp.iterdir():
                if ad.is_dir():
                    for pd in ad.iterdir():
                        if pd.is_dir() and (pd / "main.py").exists(): return True
        return False

    def _bootstrap_installation(self): Log.info("plugin-loader", "跳过引导安装（pkg 插件已移除）")

    def _sort_by_dependencies(self, dep_plugin):
        if not dep_plugin: return
        for n, i in self.plugins.items(): dep_plugin.add_plugin(n, i["info"].dependencies)
        try:
            order = dep_plugin.resolve()
            sp = {}
            for n in order:
                if n in self.plugins: sp[n] = self.plugins[n]
            for n in set(self.plugins.keys()) - set(sp.keys()): sp[n] = self.plugins[n]
            self.plugins = sp
        except Exception as e: Log.error("plugin-loader", f"依赖解析失败: {e}")

    def _link_capabilities(self):
        for pn, info in self.plugins.items():
            for cap in info["info"].capabilities:
                if self.capability_registry.has_capability(cap):
                    for cn in self.capability_registry.get_consumers(cap):
                        if cn in self.plugins:
                            ci = self.plugins[cn]["info"]
                            ca = self.plugins[cn].get("permissions", [])
                            try:
                                p = self.capability_registry.get_provider(cap, requester=cn, allowed_plugins=ca)
                                if p and hasattr(ci, "extensions"): ci.extensions[f"_{cap}_provider"] = p
                            except PermissionError as e: Log.error("plugin-loader", f"权限拒绝: {e}")

    def start_all(self):
        self._inject_dependencies()
        for n, i in self.plugins.items():
            try: i["instance"].start()
            except Exception as e: Log.error("plugin-loader", f"启动失败 {n}: {e}")

    def init_and_start_all(self):
        Log.info("plugin-loader", f"init_and_start_all 被调用，plugins={len(self.plugins)}")
        self._inject_dependencies()
        ordered = self._get_ordered_plugins()
        Log.tip("plugin-loader", f"插件启动顺序: {' -> '.join(ordered)}")
        for name in ordered:
            if "plugin-loader" in name: continue
            try:
                Log.info("plugin-loader", f"初始化: {name}")
                self.plugins[name]["instance"].init()
            except Exception as e: Log.error("plugin-loader", f"初始化失败 {name}: {e}")
        for name in ordered:
            if "plugin-loader" in name: continue
            try:
                Log.info("plugin-loader", f"启动: {name}")
                self.plugins[name]["instance"].start()
            except Exception as e: Log.error("plugin-loader", f"启动失败 {name}: {e}")

    def _get_ordered_plugins(self) -> list[str]:
        if not self._dependency_plugin: return list(self.plugins.keys())
        try: return [n for n in self._dependency_plugin.resolve() if n in self.plugins]
        except Exception as e: Log.warn("plugin-loader", f"依赖解析失败，使用原始顺序: {e}"); return list(self.plugins.keys())

    def _inject_dependencies(self):
        Log.info("plugin-loader", f"开始注入依赖，共 {len(self.plugins)} 个插件")
        nm = {}
        for n in self.plugins:
            c = n.rstrip("}"); nm[c] = n; nm[c + "}"] = n
        for n, i in self.plugins.items():
            inst = i["instance"]; io = i.get("info")
            if not io or not io.dependencies: continue
            for dn in io.dependencies:
                ad = nm.get(dn) or nm.get(dn + "}")
                if ad and ad in self.plugins:
                    sn = f"set_{dn.replace('-', '_')}"
                    if hasattr(inst, sn):
                        try: getattr(inst, sn)(self.plugins[ad]["instance"]); Log.ok("plugin-loader", f"注入成功: {n} <- {ad}")
                        except Exception as e: Log.error("plugin-loader", f"注入依赖失败 {n}.{sn}: {e}")
                    else: Log.warn("plugin-loader", f"{n} 没有 {sn} 方法")

    def stop_all(self):
        for n, i in reversed(list(self.plugins.items())):
            try: i["instance"].stop()
            except Exception as e: Log.error("plugin-loader", f"插件 {n} 停止失败：{type(e).__name__}: {e}")
        if self.lifecycle_plugin: self.lifecycle_plugin.stop_all()

    def get_info(self, name: str) -> Optional[PluginInfo]:
        if name in self.plugins: return self.plugins[name]["info"]
        return None

    def has_capability(self, capability: str) -> bool: return self.capability_registry.has_capability(capability)
    def get_capability_provider(self, capability: str) -> Optional[Any]: return self.capability_registry.get_provider(capability)


class PluginLoaderPlugin(Plugin):
    """插件加载器插件"""
    def __init__(self):
        self.manager = PluginManager()
        self._loaded = False
        self._started = False
        self._ensure_plugin_package()

    def _ensure_plugin_package(self):
        if 'plugin' not in sys.modules:
            pkg = types.ModuleType('plugin'); pkg.__path__ = []; sys.modules['plugin'] = pkg

    def init(self, deps: dict = None):
        if self._loaded: return
        self._loaded = True
        self._ensure_plugin_package()
        Log.info("plugin-loader", "开始加载插件...")
        self.manager.load_all()

    def start(self):
        if self._started: return
        self._started = True
        Log.info("plugin-loader", "启动插件...")
        self.manager.init_and_start_all()

    def stop(self):
        Log.info("plugin-loader", "停止插件...")
        self.manager.stop_all()


register_plugin_type("PluginManager", PluginManager)
register_plugin_type("PluginInfo", PluginInfo)
register_plugin_type("CapabilityRegistry", CapabilityRegistry)
register_plugin_type("PLInjector", PLInjector)


def New():
    return PluginLoaderPlugin()
