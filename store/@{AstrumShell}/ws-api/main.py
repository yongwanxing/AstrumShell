"""WebSocket API 插件入口 - 简化版"""
from oss.logger.logger import Log
from oss.plugin.types import Plugin, register_plugin_type


class WsApiPlugin(Plugin):
    """WebSocket API 插件"""

    def __init__(self):
        self._running = False

    def init(self, deps: dict = None):
        """初始化"""
        Log.info("ws-api", "初始化完成")

    def start(self):
        """启动"""
        self._running = True
        Log.info("ws-api", "已启动")

    def stop(self):
        """停止"""
        self._running = False
        Log.error("ws-api", "已停止")


register_plugin_type("WsApiPlugin", WsApiPlugin)


def New():
    return WsApiPlugin()
