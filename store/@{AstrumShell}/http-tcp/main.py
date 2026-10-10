"""HTTP TCP 插件入口"""
from oss.plugin.types import Plugin, register_plugin_type
from .server import TcpHttpServer
from .router import TcpRouter
from .middleware import TcpMiddlewareChain


class HttpTcpPlugin(Plugin):
    """HTTP TCP 插件"""

    def __init__(self):
        self.server = None
        self.router = TcpRouter()
        self.middleware = TcpMiddlewareChain()

    def init(self, deps: dict = None):
        """初始化"""
        self.server = TcpHttpServer(self.router, self.middleware)

    def start(self):
        """启动"""
        self.server.start()

    def stop(self):
        """停止"""
        if self.server:
            self.server.stop()


register_plugin_type("HttpTcpPlugin", HttpTcpPlugin)


def New():
    return HttpTcpPlugin()
