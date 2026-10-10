"""Web 工具包 - 路由注册、静态文件服务、前端事件（不负责渲染）"""
import json
import sys
from pathlib import Path
from oss.plugin.types import Plugin, register_plugin_type, Response
from .router import WebRouter
from .static import StaticFileHandler
from .template import TemplateEngine


class _Log:
    _TTY = sys.stdout.isatty()
    _C = {"reset": "\033[0m", "white": "\033[0;37m", "yellow": "\033[1;33m", "blue": "\033[1;34m", "red": "\033[1;31m"}
    @classmethod
    def _c(cls, t, c):
        return f"{cls._C.get(c,'')}{t}{cls._C['reset']}" if cls._TTY else t
    @classmethod
    def info(cls, m): print(f"{cls._c('[web-toolkit]', 'white')} {cls._c(m, 'white')}")
    @classmethod
    def warn(cls, m): print(f"{cls._c('[web-toolkit]', 'yellow')} {cls._c('⚠', 'yellow')} {cls._c(m, 'yellow')}")
    @classmethod
    def error(cls, m): print(f"{cls._c('[web-toolkit]', 'red')} {cls._c('✗', 'red')} {cls._c(m, 'red')}")


class WebToolkitPlugin(Plugin):
    """Web 工具包插件 - 提供网站前端所有服务"""

    def __init__(self):
        self.router = None
        self.static_handler = None
        self.template_engine = None
        self.http_api = None
        self.http_tcp = None
        self.storage = None
        self.config = {}  # 从 config.json 读取
        self.root_dir = None

    def init(self, deps: dict = None):
        """初始化 - 读取 config.json 配置"""
        self.router = WebRouter()
        self.template_engine = TemplateEngine()
        self._load_config()
        self.static_handler = StaticFileHandler(root=str(self.root_dir))
        _Log.info(f"配置加载完成: root_dir={self.root_dir}")

    def start(self):
        """启动"""
        # 注册路由到 http-api
        if self.http_api:
            http_instance = self.http_api
            if hasattr(http_instance, "router"):
                # 精确路由先注册，参数化路由后注册
                http_instance.router.get(
                    self.config.get("website_prefix", "/website") + "/",
                    self._serve_website_index
                )
                http_instance.router.get(
                    self.config.get("website_prefix", "/website") + "/:path",
                    self._serve_static
                )
                http_instance.router.get(
                    self.config.get("static_prefix", "/static") + "/:path",
                    self._serve_static
                )

        # 注册路由到 http-tcp
        if self.http_tcp:
            tcp_instance = self.http_tcp
            if hasattr(tcp_instance, "router"):
                tcp_instance.router.get(
                    self.config.get("website_prefix", "/website") + "/",
                    self._serve_website_index
                )
                tcp_instance.router.get(
                    self.config.get("website_prefix", "/website") + "/:path",
                    self._serve_static
                )
                tcp_instance.router.get(
                    self.config.get("static_prefix", "/static") + "/:path",
                    self._serve_static
                )

        _Log.info("Web 工具包已启动")

    def stop(self):
        """停止"""
        pass

    def set_http_api(self, instance):
        """设置 HTTP API 实例"""
        self.http_api = instance

    def set_http_tcp(self, instance):
        """设置 HTTP TCP 实例"""
        self.http_tcp = instance

    def set_plugin_storage(self, instance):
        """设置 plugin-storage 实例（唯一文件读写入口）"""
        self.storage = instance

    def set_static_dir(self, path: str):
        """设置静态文件目录"""
        self.static_handler.set_root(path)

    def set_template_dir(self, path: str):
        """设置模板目录"""
        template_root = Path(path)
        if template_root.exists():
            self.template_engine.set_root(str(template_root))

    def _load_config(self):
        """读取 config.json，解析网站根目录"""
        config_path = Path("./data/web-toolkit/config.json")
        if not config_path.exists():
            _Log.warn("config.json 不存在，使用默认配置")
            self.config = {
                "root_dir": "../website",
                "index_file": "index.html",
                "static_prefix": "/static",
                "website_prefix": "/website",
            }
        else:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)

        # 解析根目录（相对于 config.json 的路径）
        root_relative = self.config.get("root_dir", "../website")
        self.root_dir = (config_path.parent / root_relative).resolve()

        # 初始化模板引擎
        template_dir = self.config.get("template_dir", "")
        if template_dir:
            template_path = self.root_dir / template_dir
            if template_path.exists():
                self.template_engine.set_root(str(template_path))

    def _serve_website_index(self, request):
        """提供 website 目录首页"""
        index_file = self.config.get("index_file", "index.html")
        if self.root_dir:
            path = self.root_dir / index_file
            if path.exists():
                content = path.read_text(encoding="utf-8")
                return Response(
                    status=200,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    body=content
                )
        return Response(status=404, body="Index file not found")

    def _serve_static(self, request):
        """提供静态文件"""
        path = request.path
        website_prefix = self.config.get("website_prefix", "/website")
        static_prefix = self.config.get("static_prefix", "/static")

        if path.startswith(website_prefix + "/"):
            filename = path[len(website_prefix) + 1:]
        elif path.startswith(static_prefix + "/"):
            filename = path[len(static_prefix) + 1:]
        else:
            filename = path.lstrip("/")

        # 安全检查：防止路径穿越
        if ".." in filename or filename.startswith("/"):
            return Response(status=403, body="Forbidden")

        if not filename:
            return self._serve_website_index(request)
        return self.static_handler.serve(filename)


register_plugin_type("WebToolkitPlugin", WebToolkitPlugin)


def New():
    return WebToolkitPlugin()
