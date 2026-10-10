"""HTML 渲染服务 - 通过 config.json 配置，统一文件入口"""
import json
import sys
from pathlib import Path
from oss.plugin.types import Plugin, register_plugin_type, Response


class _Log:
    _TTY = sys.stdout.isatty()
    _C = {"reset": "\033[0m", "white": "\033[0;37m", "yellow": "\033[1;33m", "blue": "\033[1;34m", "red": "\033[1;31m"}
    @classmethod
    def _c(cls, t, c):
        return f"{cls._C.get(c,'')}{t}{cls._C['reset']}" if cls._TTY else t
    @classmethod
    def info(cls, m): print(f"{cls._c('[html-render]', 'white')} {cls._c(m, 'white')}")
    @classmethod
    def warn(cls, m): print(f"{cls._c('[html-render]', 'yellow')} {cls._c('⚠', 'yellow')} {cls._c(m, 'yellow')}")
    @classmethod
    def error(cls, m): print(f"{cls._c('[html-render]', 'red')} {cls._c('✗', 'red')} {cls._c(m, 'red')}")


class HtmlRenderPlugin(Plugin):
    """HTML 渲染插件 - 渲染服务由 html-render 提供"""

    def __init__(self):
        self.http_api = None
        self.storage = None  # plugin-storage 入口
        self.config = {}
        self.root_dir = None  # 解析后的网站根目录

    def init(self, deps: dict = None):
        """初始化 - 读取 config.json 并解析网站根目录"""
        self._load_config()
        _Log.info(f"配置加载完成: root_dir={self.root_dir}")

    def start(self):
        """启动 - 注册路由到 http-api，共享配置给 web-toolkit"""
        # 注册首页路由
        if self.http_api and hasattr(self.http_api, 'router'):
            self.http_api.router.get("/", self._serve_html)
            _Log.info("已注册路由到 http-api")
        else:
            _Log.warn("http-api 未加载")

        # 将配置共享给 web-toolkit（通过 plugin-storage 的 DCIM 共享存储）
        if self.storage:
            shared = self.storage.get_shared()
            shared.set_shared("html-render-config", {
                "root_dir": str(self.root_dir),
                "index_file": self.config.get("index_file", "index.html"),
                "static_prefix": self.config.get("static_prefix", "/static"),
            })
            _Log.info("配置已共享到 DCIM")

    def stop(self):
        """停止"""
        pass

    def set_http_api(self, instance):
        """设置 http-api 实例"""
        self.http_api = instance

    def set_plugin_storage(self, instance):
        """设置 plugin-storage 实例（唯一文件读写入口）"""
        self.storage = instance

    def _load_config(self):
        """读取 config.json，解析根目录"""
        config_path = Path("./data/html-render/config.json")
        if not config_path.exists():
            _Log.warn("config.json 不存在，使用默认配置")
            self.config = {"root_dir": "../website", "index_file": "index.html"}
        else:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)

        # 解析根目录（相对于 config.json 的路径）
        root_relative = self.config.get("root_dir", "../website")
        self.root_dir = (config_path.parent / root_relative).resolve()

    def _serve_html(self, request):
        """提供 HTML 页面 - 通过 plugin-storage 读取并注入静态资源路径"""
        index_file = self.config.get("index_file", "index.html")
        
        # 安全检查：防止路径穿越
        if ".." in index_file or index_file.startswith("/"):
            return Response(status=403, body="Forbidden")
        
        if self.storage:
            storage = self.storage.get_storage("html-render")
            if storage.file_exists(index_file):
                content = storage.read_file(index_file)
                if content:
                    # 注入静态资源路径（相对路径 → /website/ 前缀）
                    content = self._inject_static_paths(content)
                    return Response(
                        status=200,
                        headers={"Content-Type": "text/html; charset=utf-8"},
                        body=content
                    )
        return Response(status=404, body="Not Found")

    def _inject_static_paths(self, html: str) -> str:
        """将相对静态资源路径替换为 /website/ 前缀"""
        import re
        # href="css/xxx" → href="/website/css/xxx"
        html = re.sub(r'(href\s*=\s*["\'])css/', r'\1/website/css/', html)
        # src="js/xxx" → src="/website/js/xxx"
        html = re.sub(r'(src\s*=\s*["\'])js/', r'\1/website/js/', html)
        # src="logo.svg" → src="/website/logo.svg"
        html = re.sub(r'(src\s*=\s*["\'])(?!https?://|/)([\w.-]+\.(svg|png|jpg|gif|ico|webp))', r'\1/website/\2', html)
        return html


register_plugin_type("HtmlRenderPlugin", HtmlRenderPlugin)


def New():
    return HtmlRenderPlugin()
