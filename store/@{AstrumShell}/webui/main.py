"""WebUI - Web 控制台 (容器模式)"""
from pathlib import Path
from oss.logger.logger import Log
from oss.plugin.types import Plugin, Response, register_plugin_type
from oss.config import get_config
from .core.server import WebUIServer


class WebUIPlugin(Plugin):
    """WebUI 插件 - 提供页面容器"""

    def __init__(self):
        self.http_api = None
        self.server = None
        self.config = {}

    def meta(self):
        from oss.plugin.types import Metadata, PluginConfig, Manifest
        config = get_config()
        return Manifest(
            metadata=Metadata(
                name="webui",
                version="2.1.0",
                author="AstrumShell",
                description="Web 控制台容器 - 供其他插件注册页面"
            ),
            config=PluginConfig(
                enabled=True,
                args={
                    "port": config.get("HTTP_API_PORT", 8080),
                    "theme": "dark",
                    "title": "AstrumShell"
                }
            ),
            dependencies=["http-api"]
        )

    def set_http_api(self, http_api):
        """注入 http-api"""
        self.http_api = http_api

    def init(self, deps: dict = None):
        """初始化 WebUI 服务器"""
        if not self.http_api:
            Log.error("webui", "错误: 未找到 http-api 依赖")
            return

        config = {}
        if deps:
            config = deps.get("config", {})

        self.config = {
            "port": config.get("port", get_config().get("HTTP_API_PORT", 8080)),
            "theme": config.get("theme", "dark"),
            "title": config.get("title", "AstrumShell")
        }

        # 使用 http-api 的路由器
        self.server = WebUIServer(
            self.http_api.router,
            self.config
        )
        Log.info("webui", "容器初始化完成")

    def start(self):
        """启动服务器（注册默认路由）"""
        if self.server:
            # 检测仪表盘是否已安装，自动设为首页
            self._setup_home_page()
            
            self.server.start()
            Log.info("webui", f"WebUI 容器已启动: http://localhost:{self.config['port']}")

    def _setup_home_page(self):
        """设置首页：如果仪表盘已安装则跳转到仪表盘，否则显示默认首页"""
        # 通过文件系统检查 dashboard 是否存在
        dashboard_exists = False
        store_dirs = [
            Path("store/@{AstrumShell}/dashboard"),
        ]
        for d in store_dirs:
            if d.exists() and (d / "main.py").exists():
                dashboard_exists = True
                break
        
        if dashboard_exists:
            # 仪表盘已安装，注册首页重定向到仪表盘
            self.server.router.get("/", self._handle_home_redirect)
            Log.info("webui", "检测到仪表盘，首页自动跳转到 /dashboard")
        else:
            # 默认首页
            self.server.register_page(
                path="/",
                content_provider=self.server._default_home_content,
                nav_item={'icon': 'ri-home-4-line', 'text': '首页'}
            )

    def _handle_home_redirect(self, request):
        """处理首页重定向到仪表盘"""
        return Response(
            status=302,
            headers={"Location": "/dashboard", "Content-Type": "text/html"},
            body=""
        )

    def stop(self):
        Log.error("webui", "WebUI 容器已停止")

    # --- 公开 API 供其他插件调用 ---

    def register_page(self, path: str, content_provider, nav_item: dict = None):
        """
        其他插件调用此方法注册页面。
        :param path: 路由路径 (e.g., '/dashboard')
        :param content_provider: 无参函数，返回 HTML 字符串
        :param nav_item: 导航项 {'icon': '📊', 'text': '仪表盘'}
        """
        if self.server:
            self.server.register_page(path, content_provider, nav_item)
        else:
            Log.warn("webui", f"警告: 试图注册页面 {path}，但服务器未初始化")

    def add_nav_item(self, item: dict):
        """仅添加导航项（如果页面由其他方式处理）"""
        if self.server:
            self.server.nav_items.append(item)


register_plugin_type("WebUIPlugin", WebUIPlugin)


def New():
    return WebUIPlugin()
