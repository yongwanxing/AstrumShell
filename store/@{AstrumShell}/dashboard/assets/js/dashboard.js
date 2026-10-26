/**
 * 仪表盘实时刷新
 * - 数据来源：/api/dashboard/stats（当前值）与 /api/dashboard/history（趋势）
 * - 不再整页 reload：只更新数字、表盘与 canvas 曲线
 * - 页面隐藏时暂停轮询；请求失败自动退避并提示离线
 */
(function () {
    'use strict';

    var dataNode = document.getElementById('dashboard-data');
    if (!dataNode) return;

    var DATA = {};
    try {
        DATA = JSON.parse(dataNode.textContent || '{}');
    } catch (e) {
        DATA = {};
    }
    var L = DATA.labels || {};

    var C = 2 * Math.PI * 52;          // 表盘周长（与 SVG 里的 r=52 对应）
    var COLORS = {
        cpu: '#4a90d9',
        ram: '#f5576c',
        net_recv: '#00b8a9',
        net_sent: '#f39c12',
        disk_read: '#f39c12',
        disk_write: '#e67e22',
        latency: '#9b59b6'
    };

    var el = {
        state: document.getElementById('dash-state'),
        last: document.getElementById('dash-last'),
        toggle: document.getElementById('dash-toggle'),
        refresh: document.getElementById('dash-refresh'),
        interval: document.getElementById('dash-interval'),
        window: document.getElementById('dash-window')
    };

    var storageKey = 'dashboard.refresh_interval';
    var interval = Number(DATA.interval) || 2;
    try {
        var cached = Number(localStorage.getItem(storageKey));
        if (cached >= 1 && cached <= 60) interval = cached;
    } catch (e) { /* 忽略 */ }
    if (el.interval) el.interval.value = String(interval);

    var paused = false;
    var timer = null;
    var failures = 0;

    // ---------- 工具 ----------

    function text(id, value) {
        var node = document.getElementById(id);
        if (node) node.textContent = value;
    }

    function fmtBytes(rate) {
        if (!rate) return '0 B/s';
        var units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
        var i = 0;
        while (rate >= 1024 && i < units.length - 1) { rate /= 1024; i += 1; }
        return rate.toFixed(rate >= 10 || i === 0 ? 0 : 1) + ' ' + units[i];
    }

    function clock(ts) {
        if (!ts) return '';
        var d = new Date(ts * 1000);
        var pad = function (n) { return (n < 10 ? '0' : '') + n; };
        return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
    }

    function setState(message, kind) {
        if (!el.state) return;
        el.state.textContent = message;
        el.state.className = 'dash-state' + (kind ? ' ' + kind : '');
    }

    // ---------- 表盘 ----------

    function setGauge(key, percent, extra) {
        var ring = document.getElementById('gauge-' + key);
        var value = Math.max(0, Math.min(100, Number(percent) || 0));
        if (ring) {
            ring.setAttribute('stroke-dashoffset', String(C * (1 - value / 100)));
            ring.setAttribute('class', 'gauge-fill gauge-' + (value < 60 ? 'ok' : value < 85 ? 'warn' : 'err'));
        }
        text('gauge-' + key + '-text', value.toFixed(1) + '%');
        if (extra) text('gauge-' + key + '-extra', extra);
    }

    // ---------- 曲线 ----------

    function setupCanvas(canvas) {
        var ratio = window.devicePixelRatio || 1;
        var width = canvas.clientWidth || (canvas.parentElement && canvas.parentElement.clientWidth) || 260;
        canvas.width = Math.max(1, Math.round(width * ratio));
        canvas.height = Math.max(1, Math.round(64 * ratio));
        var ctx = canvas.getContext('2d');
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        return { ctx: ctx, width: width, height: 64 };
    }

    function drawChart(key, series, opts) {
        var canvas = document.getElementById('chart-' + key);
        if (!canvas) return;
        opts = opts || {};
        var c = setupCanvas(canvas);
        var ctx = c.ctx;

        var border = (getComputedStyle(document.documentElement).getPropertyValue('--border') || '').trim() || '#2a2f3a';
        ctx.clearRect(0, 0, c.width, c.height);
        ctx.strokeStyle = border;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, c.height - 0.5);
        ctx.lineTo(c.width, c.height - 0.5);
        ctx.stroke();

        var all = [];
        series.forEach(function (s) { all = all.concat(s.values || []); });
        var max = opts.max || Math.max.apply(null, all.concat([1]));
        var points = Math.max.apply(null, series.map(function (s) {
            return (s.values || []).length;
        }).concat([0]));
        if (!points) return;
        var stepX = points > 1 ? c.width / (points - 1) : 0;

        series.forEach(function (s) {
            var values = s.values || [];
            if (!values.length) return;
            ctx.beginPath();
            values.forEach(function (value, index) {
                var x = index * stepX;
                var y = c.height - Math.max(0, Math.min(1, value / max)) * (c.height - 6) - 2;
                if (index === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.strokeStyle = s.color;
            ctx.lineWidth = 2;
            ctx.stroke();

            if (opts.fill && values.length > 1) {
                var grad = ctx.createLinearGradient(0, 0, 0, c.height);
                grad.addColorStop(0, s.color + '55');
                grad.addColorStop(1, s.color + '00');
                ctx.lineTo(c.width - (points - values.length) * stepX, c.height);
                ctx.lineTo(0, c.height);
                ctx.closePath();
                ctx.fillStyle = grad;
                ctx.fill();
            }
        });
    }

    // ---------- 渲染 ----------

    function renderStats(s) {
        var cpuCores = (s.cpu && s.cpu.cores) || 0;
        setGauge('cpu', s.cpu && s.cpu.percent,
            (L.cores || '{{count}} cores').replace('{{count}}', cpuCores));
        setGauge('ram', s.ram && s.ram.percent,
            (s.ram ? s.ram.used + ' / ' + s.ram.total + ' GB' : ''));
        setGauge('disk', s.disk && s.disk.percent,
            (s.disk ? s.disk.used + ' / ' + s.disk.total + ' GB' : ''));

        text('info-uptime', s.uptime || '—');
        text('info-processes', s.processes != null ? String(s.processes) : '—');
        text('info-load', s.load ? s.load.load1 + ' / ' + s.load.load5 + ' / ' + s.load.load15 : '—');
        text('chart-latency-val', s.latency != null ? s.latency + ' ms' : '—');
        text('chart-net-val', s.network
            ? '↓' + fmtBytes(s.network.recv_rate) + ' ↑' + fmtBytes(s.network.sent_rate) : '—');
        text('chart-diskio-val', s.disk_io
            ? 'R' + fmtBytes(s.disk_io.read_rate) + ' W' + fmtBytes(s.disk_io.write_rate) : '—');

        renderHost(s.host || {});
        setState(L.live || 'Live', 'ok');
        if (el.last) el.last.textContent = (L.last_update || 'Last update') + ': ' + clock(s.sampled_at);
    }

    function renderHistory(h) {
        var count = h.max_len || (h.cpu || []).length;
        if (el.window) {
            el.window.textContent = (L.trend || 'Last {{count}} samples')
                .replace('{{count}}', String(count));
        }
        drawChart('cpu', [{ values: h.cpu || [], color: COLORS.cpu }], { max: 100, fill: true });
        drawChart('ram', [{ values: h.ram || [], color: COLORS.ram }], { max: 100, fill: true });
        drawChart('net', [
            { values: h.net_recv || [], color: COLORS.net_recv },
            { values: h.net_sent || [], color: COLORS.net_sent }
        ], {});
        drawChart('diskio', [
            { values: h.disk_read || [], color: COLORS.disk_read },
            { values: h.disk_write || [], color: COLORS.disk_write }
        ], {});
        drawChart('latency', [{ values: h.latency || [], color: COLORS.latency }], { fill: true });
    }

    function renderHost(extra) {
        text('info-os', extra.os || '—');
        text('info-python', extra.python || '—');
        text('info-hostname', extra.hostname || '—');
    }

    // ---------- 数据获取 ----------

    function fetchJSON(url) {
        return fetch(url, { cache: 'no-store' }).then(function (resp) {
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            return resp.json();
        });
    }

    function tick(force) {
        if (!document.getElementById('dash-state')) {     // 页面已被替换，停止轮询
            stop();
            return;
        }
        if (paused && !force) return;
        if (document.hidden && !force) return;

        Promise.all([
            fetchJSON('/api/dashboard/stats'),
            fetchJSON('/api/dashboard/history')
        ]).then(function (result) {
            failures = 0;
            renderStats(result[0]);
            renderHistory(result[1]);
            schedule(interval);
        }).catch(function (err) {
            failures += 1;
            setState((L.error || 'Failed to fetch metrics') + ' (' + err.message + ')', 'error');
            // 退避重试：最多拉长到 30 秒
            schedule(Math.min(30, interval * Math.pow(1.6, failures)));
        });
    }

    function schedule(seconds) {
        stop();
        if (paused) return;
        timer = setTimeout(function () { tick(); }, Math.max(1, seconds) * 1000);
    }

    function stop() {
        if (timer) {
            clearTimeout(timer);
            timer = null;
        }
    }

    // ---------- 控件 ----------

    if (el.toggle) {
        el.toggle.addEventListener('click', function () {
            paused = !paused;
            el.toggle.textContent = paused ? (L.resume || 'Resume') : (L.pause || 'Pause');
            setState(paused ? (L.paused || 'Paused') : (L.live || 'Live'), paused ? '' : 'ok');
            if (paused) stop();
            else tick(true);
        });
    }

    if (el.refresh) {
        el.refresh.addEventListener('click', function () { tick(true); });
    }

    if (el.interval) {
        el.interval.addEventListener('change', function () {
            interval = Number(el.interval.value) || 2;
            try {
                localStorage.setItem(storageKey, String(interval));
            } catch (e) { /* 忽略 */ }
            // 同步到服务端设置（有 /api/settings 时），让设置页也能看到
            try {
                fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        dashboard_refresh_interval: interval,
                        dashboard_auto_refresh: true
                    })
                }).catch(function () { /* 设置页不可用则只存在本地 */ });
            } catch (e) { /* 忽略 */ }
            schedule(interval);
        });
    }

    document.addEventListener('visibilitychange', function () {
        if (!document.hidden && !paused) tick(true);
    });

    window.addEventListener('beforeunload', stop);

    // 首次拉取（数据由 /api/dashboard/* 提供）
    tick(true);
})();
