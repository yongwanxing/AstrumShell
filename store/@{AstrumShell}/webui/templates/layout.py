"""页面布局模板"""


class LayoutTemplate:
    """布局模板"""

    def __init__(self, config: dict):
        self.config = config

    def render(self) -> str:
        """渲染页面"""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.config.get('title', 'AstrumShell')}</title>
    <link rel="stylesheet" href="/static/css/main.css">
</head>
<body>
    <div class="app">
        <aside class="sidebar">
            <div class="sidebar-header">
                <h1>🚀 {self.config.get('title', 'AstrumShell')}</h1>
            </div>
            <nav class="sidebar-nav">
                <a href="/" class="nav-item active">
                    <span class="nav-icon">🏠</span>
                    <span class="nav-text">首页</span>
                </a>
            </nav>
            <div class="sidebar-footer">
                <button class="settings-btn">⚙️ 设置</button>
            </div>
        </aside>
        <main class="content">
            <header class="content-header">
                <h2>欢迎使用 AstrumShell</h2>
            </header>
            <div class="content-body">
                <div class="empty-state">
                    <p>暂无内容</p>
                </div>
            </div>
        </main>
    </div>
    <script src="/static/js/main.js"></script>
</body>
</html>"""
