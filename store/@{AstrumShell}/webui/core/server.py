"""WebUI 服务器 - 容器模式"""
import subprocess
import os
import tempfile
from oss.plugin.types import Response
from pathlib import Path


class WebUIServer:
    """WebUI 服务器"""

    def __init__(self, router, config: dict):
        self.router = router
        self.config = config
        self.frontend_dir = Path(__file__).parent.parent / "frontend"
        
        # 页面注册表
        self.pages = {}  # path -> content_provider
        self.nav_items = []  # 导航项列表

    def start(self):
        """注册默认路由"""
        # 静态资源
        self.router.get("/static/css/main.css", self._handle_css)
        self.router.get("/static/js/main.js", self._handle_js)
        self.router.get("/health", self._handle_health)

    def register_page(self, path: str, content_provider, nav_item: dict = None):
        """供其他插件注册页面"""
        self.pages[path] = content_provider
        if nav_item:
            nav_item['url'] = path
            self.nav_items.append(nav_item)
        
        # 注册路由
        self.router.get(path, lambda req: self._render_page(path, req))

    def _render_page(self, path: str, request):
        """渲染页面布局 + 内容"""
        provider = self.pages.get(path)
        content = provider() if provider else ""
        
        # 排序导航项（首页在前）
        sorted_nav = sorted(self.nav_items, key=lambda x: 0 if x.get('url') == '/' else 1)

        # 构建导航项 HTML
        nav_html = ""
        icon_map = {
            '🏠': 'ri-home-4-line',
            '📊': 'ri-dashboard-line',
            '📋': 'ri-file-list-3-line',
            '🧩': 'ri-puzzle-line',
            '⚙️': 'ri-settings-3-line',
            '🔌': 'ri-plug-line',
            '📦': 'ri-box-3-line',
            '🌐': 'ri-global-line',
        }
        for item in sorted_nav:
            url = item.get('url', '#')
            is_active = 'active' if url == path else ''
            icon = item.get('icon', 'ri-dashboard-line')
            text = item.get('text', '')
            ri_icon = icon_map.get(icon, icon)
            title = text
            nav_html += f'''
                <a href="{url}" class="nav-item {is_active}" title="{title}">
                    <i class="{ri_icon}"></i>
                </a>
            '''

        page_title = self.config.get("title", "AstrumShell")
        
        # 读取 HTML 模板
        template_file = self.frontend_dir / "views" / "layout.html"
        with open(template_file, 'r', encoding='utf-8') as f:
            html_template = f.read()
        
        html = html_template.replace('{{ pageTitle }}', page_title)
        html = html.replace('{{ navItems }}', nav_html)
        html = html.replace('{{ content }}', content)
        
        return Response(
            status=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            body=html
        )
    def _default_home_content(self) -> str:
        """默认首页内容"""
        return """
        <div class="home-content">
            <div class="welcome-banner">
                <h2>👋 欢迎使用 AstrumShell</h2>
                <p>一切皆为插件的轻量级框架</p>
            </div>
        </div>
        """

    def _execute_php(self, php_file: str, variables: dict = None) -> str:
        """执行 PHP 文件"""
        variables = variables or {}

        # 构建 PHP 变量注入
        php_vars = ""
        for key, value in variables.items():
            if isinstance(value, dict):
                php_vars += f"${key} = {self._php_array(value)};\n"
            elif isinstance(value, list):
                php_vars += f"${key} = {self._php_array_list(value)};\n"
            elif isinstance(value, str):
                php_vars += f"${key} = '{value.replace(chr(39), chr(92) + chr(39))}';\n"
            else:
                php_vars += f"${key} = {str(value).lower() if isinstance(value, bool) else value};\n"

        with open(php_file, 'r', encoding='utf-8') as f:
            php_content = f.read()

        # 临时文件必须和 views 在同一目录，这样 __DIR__ 才能正确解析
        views_dir = str(Path(php_file).parent)
        tmp_file = os.path.join(views_dir, '.temp_render.php')

        try:
            with open(tmp_file, 'w', encoding='utf-8') as f:
                f.write(f"<?php\n{php_vars}\n?>\n{php_content}")

            result = subprocess.run(
                ["php", "-f", tmp_file],
                capture_output=True, text=True, timeout=10, cwd=views_dir,
                encoding='utf-8', errors='replace'
            )

            if result.returncode != 0:
                print(f"[webui] PHP 执行错误: {result.stderr}")
                return f"<div class='error'>PHP Error: {result.stderr}</div>"

            return result.stdout
        finally:
            try:
                if os.path.exists(tmp_file):
                    os.unlink(tmp_file)
            except:
                pass

    def _php_array(self, py_dict: dict) -> str:
        """Python Dict -> PHP Array"""
        items = []
        for key, value in py_dict.items():
            if isinstance(value, str):
                items.append(f"'{key}' => '{value.replace(chr(39), chr(92) + chr(39))}'")
            elif isinstance(value, dict):
                items.append(f"'{key}' => {self._php_array(value)}")
            else:
                items.append(f"'{key}' => {value}")
        return "[" + ", ".join(items) + "]"

    def _php_array_list(self, py_list: list) -> str:
        """Python List -> PHP Array"""
        items = []
        for item in py_list:
            if isinstance(item, dict):
                items.append(self._php_array(item))
            elif isinstance(item, str):
                items.append(f"'{item.replace(chr(39), chr(92) + chr(39))}'")
            else:
                items.append(str(item))
        return "[" + ", ".join(items) + "]"

    def _handle_css(self, request):
        css_file = self.frontend_dir / "assets" / "css" / "main.css"
        with open(css_file, 'r', encoding='utf-8') as f:
            css = f.read()
        return Response(status=200, headers={"Content-Type": "text/css; charset=utf-8"}, body=css)

    def _handle_js(self, request):
        js_file = self.frontend_dir / "assets" / "js" / "main.js"
        with open(js_file, 'r', encoding='utf-8') as f:
            js = f.read()
        return Response(status=200, headers={"Content-Type": "application/javascript; charset=utf-8"}, body=js)

    def _handle_health(self, request):
        import json
        return Response(status=200, headers={"Content-Type": "application/json"}, body=json.dumps({"status": "ok"}))
