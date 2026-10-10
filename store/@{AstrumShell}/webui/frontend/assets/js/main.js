/**
 * AstrumShell WebUI 主脚本
 * 提供基础框架功能
 */

window.WebUI = {
    /**
     * 打开设置面板
     * 其他插件可以扩展此功能
     */
    openSettings: function() {
        console.log('[WebUI] 打开设置面板');
        // 设置面板逻辑 - 其他插件可以扩展
        alert('设置功能需要其他插件支持');
    },

    /**
     * 注册导航项
     * 其他插件可以调用此方法添加导航
     */
    registerNavItem: function(item) {
        console.log('[WebUI] 注册导航项:', item);
        // 实际实现需要与后端通信
    },

    /**
     * 加载内容到主内容区
     * 其他插件可以调用此方法加载内容
     */
    loadContent: function(url) {
        console.log('[WebUI] 加载内容:', url);
        // 实际实现需要 AJAX 请求
    }
};

console.log('AstrumShell WebUI 框架已加载');
