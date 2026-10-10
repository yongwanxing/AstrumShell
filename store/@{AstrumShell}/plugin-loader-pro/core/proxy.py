"""插件代理 - 防越级访问"""


class PermissionError(Exception):
    """权限错误"""
    pass


class PluginProxy:
    """插件代理"""

    def __init__(self, plugin_name: str, plugin_instance: any,
                 allowed_plugins: list[str], all_plugins: dict[str, dict]):
        self._plugin_name = plugin_name
        self._plugin_instance = plugin_instance
        self._allowed_plugins = set(allowed_plugins)
        self._all_plugins = all_plugins

    def get_plugin(self, name: str) -> any:
        """获取其他插件实例（带权限检查）"""
        if name not in self._allowed_plugins and "*" not in self._allowed_plugins:
            raise PermissionError(
                f"插件 '{self._plugin_name}' 无权访问插件 '{name}'"
            )
        if name not in self._all_plugins:
            return None
        return self._all_plugins[name]["instance"]

    def list_plugins(self) -> list[str]:
        """列出有权限访问的插件"""
        if "*" in self._allowed_plugins:
            return list(self._all_plugins.keys())
        return [n for n in self._allowed_plugins if n in self._all_plugins]

    def __getattr__(self, name: str):
        return getattr(self._plugin_instance, name)
