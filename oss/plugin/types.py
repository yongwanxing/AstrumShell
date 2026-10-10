"""插件类型定义"""
from abc import ABC, abstractmethod
from typing import Any, Optional


# ========== 插件自定义类型注册 ==========
_plugin_types: dict[str, Any] = {}


def register_plugin_type(type_name: str, type_class: Any):
    """注册插件自定义类型"""
    _plugin_types[type_name] = type_class


def get_plugin_type(type_name: str) -> Optional[Any]:
    """获取已注册的插件类型"""
    return _plugin_types.get(type_name)


def list_plugin_types() -> dict[str, Any]:
    """列出所有已注册的插件类型"""
    return _plugin_types.copy()


# ========== HTTP 响应类型 ==========
class Response:
    """HTTP 响应对象"""
    def __init__(self, status: int = 200, headers: Optional[dict[str, str]] = None, body: str = ""):
        self.status = status
        self.headers = headers or {}
        self.body = body


# ========== 插件数据类型 ==========
class Metadata:
    """插件元数据"""
    def __init__(self, name: str = "", version: str = "", author: str = "", description: str = ""):
        self.name = name
        self.version = version
        self.author = author
        self.description = description


class PluginConfig:
    """插件配置"""
    def __init__(self, enabled: bool = True, args: Optional[dict[str, Any]] = None):
        self.enabled = enabled
        self.args = args or {}


class Manifest:
    """插件清单"""
    def __init__(self, metadata: Optional[Metadata] = None, config: Optional[PluginConfig] = None, dependencies: Optional[list[str]] = None):
        self.metadata = metadata or Metadata()
        self.config = config or PluginConfig()
        self.dependencies = dependencies or []


# ========== 插件基类 ==========
class Plugin(ABC):
    """插件基类"""

    @abstractmethod
    def init(self, deps: Optional[dict[str, Any]] = None):
        """初始化插件"""
        ...

    @abstractmethod
    def start(self):
        """启动插件"""
        ...

    @abstractmethod
    def stop(self):
        """停止插件"""
        ...

    def meta(self) -> Manifest:
        """获取插件元数据"""
        return Manifest()

    def reload(self, config: Optional[dict[str, Any]] = None):
        """热重载插件配置"""
        pass

    def health(self) -> bool:
        """健康检查"""
        return True

    def stats(self) -> dict[str, Any]:
        """获取插件统计信息"""
        return {}
