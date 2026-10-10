"""HTTP API 插件 - 分散式布局"""
import json
from oss.plugin.types import Plugin, register_plugin_type
from .server import HttpServer, Response
from .router import Router
from .middleware import MiddlewareChain


class HttpApiPlugin(Plugin):
    """HTTP API 插件"""

    def __init__(self):
        self.server = None
        self.router = Router()
        self.middleware = MiddlewareChain()

    def init(self, deps: dict = None):
        """初始化"""
        # 注册基础路由
        self.router.get("/health", self._health_handler)
        self.router.get("/api/server/info", self._server_info_handler)
        self.router.get("/api/status", self._status_handler)

        self.server = HttpServer(self.router, self.middleware)

    def start(self):
        """启动"""
        self.server.start()

    def stop(self):
        """停止"""
        if self.server:
            self.server.stop()

    def _health_handler(self, request):
        """健康检查"""
        return Response(
            status=200,
            body=json.dumps({"status": "ok", "service": "http-api"}),
            headers={"Content-Type": "application/json"}
        )

    def _server_info_handler(self, request):
        """服务器信息"""
        return Response(
            status=200,
            body=json.dumps({
                "name": "AstrumShell HTTP API",
                "version": "1.0.0",
                "endpoints": ["/health", "/api/server/info", "/api/status"]
            }),
            headers={"Content-Type": "application/json"}
        )

    def _status_handler(self, request):
        """状态检查"""
        return Response(
            status=200,
            body=json.dumps({"status": "running", "plugins_loaded": True}),
            headers={"Content-Type": "application/json"}
        )


register_plugin_type("HttpApiPlugin", HttpApiPlugin)


def New():
    return HttpApiPlugin()
