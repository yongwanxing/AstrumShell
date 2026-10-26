/**
 * 设置页交互
 * 数据来自页面里的 <script id="settings-data" type="application/json">
 * 保存走 POST /api/settings，恢复默认走 POST /api/settings/reset
 */
(function () {
    'use strict';

    var dataNode = document.getElementById('settings-data');
    if (!dataNode) return;

    var DATA = {};
    try {
        DATA = JSON.parse(dataNode.textContent || '{}');
    } catch (e) {
        DATA = {};
    }
    var CURRENT = DATA.current || {};
    var TEXT = DATA.text || {};

    var statusEl = document.getElementById('settings-status');
    var saveBtn = document.getElementById('settings-save');
    var resetBtn = document.getElementById('settings-reset');
    var themeSel = document.getElementById('set-theme');
    var langSel = document.getElementById('set-language');
    var autoBox = document.getElementById('set-auto');
    var intervalBox = document.getElementById('set-interval');

    function applyTheme(theme) {
        var value = theme || 'dark';
        document.documentElement.setAttribute('data-theme', value);
        try {
            localStorage.setItem('webui.theme', value);
        } catch (e) { /* 隐私模式忽略 */ }
    }

    function setStatus(message, kind) {
        if (!statusEl) return;
        statusEl.textContent = message || '';
        statusEl.className = 'status' + (kind ? ' ' + kind : '');
    }

    function collect() {
        return {
            theme: themeSel ? themeSel.value : CURRENT.theme,
            language: langSel ? langSel.value : CURRENT.language,
            dashboard_auto_refresh: autoBox ? autoBox.checked : true,
            dashboard_refresh_interval: intervalBox ? Number(intervalBox.value) : 2
        };
    }

    function post(url, payload) {
        if (saveBtn) saveBtn.disabled = true;
        if (resetBtn) resetBtn.disabled = true;
        setStatus(TEXT.saving || '...', '');

        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload || {})
        }).then(function (resp) {
            return resp.json().catch(function () {
                return {};
            }).then(function (body) {
                if (!resp.ok) throw new Error(body.error || ('HTTP ' + resp.status));
                return body;
            });
        }).finally(function () {
            if (saveBtn) saveBtn.disabled = false;
            if (resetBtn) resetBtn.disabled = false;
        });
    }

    function failure(err) {
        var template = TEXT.save_failed || '保存失败：{{error}}';
        setStatus(template.replace('{{error}}', err && err.message ? err.message : String(err)), 'error');
    }

    // 主题即时预览（保存后服务端渲染的 data-theme 也会同步）
    if (themeSel) {
        themeSel.addEventListener('change', function () {
            applyTheme(themeSel.value);
        });
    }

    if (saveBtn) {
        saveBtn.addEventListener('click', function () {
            var payload = collect();
            var interval = payload.dashboard_refresh_interval;
            if (!(interval >= 1 && interval <= 60)) {
                setStatus(TEXT.interval_range || '1 - 60', 'error');
                return;
            }
            post('/api/settings', payload).then(function (body) {
                var saved = body.settings || {};
                setStatus(TEXT.saved || 'OK', 'ok');
                // 主题/语言影响服务端渲染的 HTML，需要重载才能生效
                if (saved.theme !== CURRENT.theme || saved.language !== CURRENT.language) {
                    setTimeout(function () { location.reload(); }, 350);
                }
            }).catch(failure);
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener('click', function () {
            post('/api/settings/reset', {}).then(function () {
                setStatus(TEXT.saved || 'OK', 'ok');
                setTimeout(function () { location.reload(); }, 350);
            }).catch(failure);
        });
    }
})();
