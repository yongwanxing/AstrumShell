/**
 * AstrumShell WebUI 主脚本（外壳）
 * - 主题启动：优先用服务端渲染的 data-theme，其次 localStorage
 * - openSettings：跳转到 /settings（设置页由 WebUI 自身提供）
 * - 供其他插件复用的轻量提示
 */

window.WebUI = {
    /**
     * 打开设置页（齿轮按钮也直接指向 /settings）
     */
    openSettings: function () {
        location.href = '/settings';
    },

    /**
     * 当前主题
     */
    theme: function () {
        return document.documentElement.getAttribute('data-theme') || 'dark';
    },

    /**
     * 切换主题（仅前端预览，持久化请在设置页保存）
     */
    setTheme: function (theme) {
        document.documentElement.setAttribute('data-theme', theme || 'dark');
        try {
            localStorage.setItem('webui.theme', theme || 'dark');
        } catch (e) { /* 忽略 */ }
    },

    /**
     * 极简轻提示（右上角浮层）
     */
    toast: function (message, kind) {
        var box = document.createElement('div');
        box.className = 'webui-toast' + (kind ? ' ' + kind : '');
        box.textContent = message || '';
        document.body.appendChild(box);
        setTimeout(function () { box.classList.add('show'); }, 10);
        setTimeout(function () {
            box.classList.remove('show');
            setTimeout(function () { box.remove(); }, 300);
        }, 2600);
    },

    /**
     * 注册导航项（客户端提示；服务端导航由插件 register_page 提供）
     */
    registerNavItem: function (item) {
        console.log('[WebUI] 注册导航项:', item);
    },

    /**
     * 加载内容到主内容区
     */
    loadContent: function (url) {
        var target = document.querySelector('.content-body');
        if (!target) return;
        fetch(url).then(function (r) { return r.text(); }).then(function (html) {
            target.innerHTML = html;
        }).catch(function (err) {
            console.warn('[WebUI] 加载失败:', err);
        });
    }
};

// 齿轮按钮（侧边栏底部）统一跳设置页
document.addEventListener('DOMContentLoaded', function () {
    var btn = document.querySelector('.settings-btn');
    if (btn && btn.tagName !== 'A') {
        btn.addEventListener('click', function () { window.WebUI.openSettings(); });
    }
});

// 本地缓存的主题优先（避免服务端与本地短暂不一致时的闪烁）
(function () {
    try {
        var cached = localStorage.getItem('webui.theme');
        if (cached) document.documentElement.setAttribute('data-theme', cached);
    } catch (e) { /* 忽略 */ }
})();

