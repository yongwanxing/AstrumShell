"""静态资源"""


class StaticAssets:
    """静态资源管理器"""

    @staticmethod
    def get_css() -> str:
        return """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f5f5f5;
    color: #333;
}

.app {
    display: flex;
    height: 100vh;
}

.sidebar {
    width: 240px;
    background: #1a1a2e;
    color: #fff;
    display: flex;
    flex-direction: column;
}

.sidebar-header {
    padding: 20px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}

.sidebar-header h1 {
    font-size: 18px;
}

.sidebar-nav {
    flex: 1;
    padding: 10px 0;
}

.nav-item {
    display: flex;
    align-items: center;
    padding: 12px 20px;
    color: #fff;
    text-decoration: none;
    transition: background 0.2s;
}

.nav-item:hover {
    background: rgba(255,255,255,0.1);
}

.nav-item.active {
    background: rgba(255,255,255,0.15);
    border-left: 3px solid #4a90d9;
}

.nav-icon {
    margin-right: 10px;
}

.sidebar-footer {
    padding: 15px 20px;
    border-top: 1px solid rgba(255,255,255,0.1);
}

.settings-btn {
    width: 100%;
    padding: 10px;
    background: rgba(255,255,255,0.1);
    border: none;
    color: #fff;
    border-radius: 6px;
    cursor: pointer;
}

.content {
    flex: 1;
    display: flex;
    flex-direction: column;
}

.content-header {
    padding: 20px 30px;
    background: #fff;
    border-bottom: 1px solid #e0e0e0;
}

.content-body {
    flex: 1;
    padding: 30px;
}

.empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #999;
}"""

    @staticmethod
    def get_js() -> str:
        return """console.log('AstrumShell WebUI loaded');"""
