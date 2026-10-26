"""插件运行时定位器

有些插件之间**无法用 setter 声明依赖**，典型的是依赖成环：
`http-api` 的 manifest 声明依赖 `i18n`（用于路由顺序），而 `i18n` 又需要在
`start()` 里拿到 `http-api` 才能注册自己的 `/api/i18n/*` 路由。若让两边互相
声明依赖，拓扑排序会检测到环。

这种情况下插件可以按名字取运行时实例：

    from oss.plugin.runtime import get_plugin
    http_api = get_plugin("http-api")

加载器（plugin-loader 的 PluginManager）在初始化时调用 :func:`set_manager`
把自身登记进来；没有加载器时所有查询安全返回 ``None``。
"""

from __future__ import annotations

from typing import Any, Optional


_manager: Optional[Any] = None


def set_manager(manager: Optional[Any]) -> None:
    """登记插件管理器（由 plugin-loader 在初始化时调用）"""
    global _manager
    _manager = manager


def get_manager() -> Optional[Any]:
    """获取当前插件管理器（可能为 None，例如单元测试或纯框架使用场景）"""
    return _manager


def get_plugin(name: str, default: Any = None) -> Any:
    """按插件名取实例，取不到返回 ``default``"""
    manager = _manager
    if manager is None:
        return default
    plugins = getattr(manager, "plugins", None)
    if not isinstance(plugins, dict):
        return default
    entry = plugins.get(name)
    if isinstance(entry, dict):
        return entry.get("instance", default)
    if entry is not None:
        return entry
    return default


def list_plugins() -> list[str]:
    """列出当前已加载的插件名"""
    manager = _manager
    plugins = getattr(manager, "plugins", None)
    return list(plugins.keys()) if isinstance(plugins, dict) else []
