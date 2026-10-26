"""Dashboard 仪表盘插件"""
import os
import time
import json
import socket
import threading
import subprocess
import platform
import psutil
from collections import deque
from oss.logger.logger import Log
from oss.plugin.types import Plugin, Response, register_plugin_type
from oss.plugin.translate import tr


class DashboardPlugin(Plugin):
    """仪表盘插件 - 依赖 WebUI 容器"""

    #: 采样间隔（秒）与保留的采样点数量
    SAMPLE_INTERVAL = 2.0
    HISTORY_LEN = 90
    #: 每 N 次采样测一次网络延迟（连接超时开销较大）
    LATENCY_EVERY = 5

    def __init__(self):
        self.webui = None
        self.views_dir = os.path.join(os.path.dirname(__file__), 'views')
        self._start_time = time.time()  # 记录插件启动时间（即项目启动时间）
        self._history_len = self.HISTORY_LEN
        self._cpu_history = deque(maxlen=self._history_len)
        self._ram_history = deque(maxlen=self._history_len)
        self._net_recv_history = deque(maxlen=self._history_len)
        self._net_sent_history = deque(maxlen=self._history_len)
        self._disk_read_history = deque(maxlen=self._history_len)
        self._disk_write_history = deque(maxlen=self._history_len)
        self._net_latency_history = deque(maxlen=self._history_len)
        self._last_net = None
        self._last_disk = None
        self._last_latency = 0.0

        # 后台采样：保证前端每次拉取都有连续趋势，且 stats 接口不用再阻塞
        self._lock = threading.Lock()
        self._sampler = None
        self._sampler_stop = threading.Event()
        self._sample_interval = self.SAMPLE_INTERVAL
        self._sample_count = 0
        self._last_stats = {}
        psutil.cpu_percent(interval=None)   # 预热：首次调用总是 0

    def meta(self):
        from oss.plugin.types import Metadata, PluginConfig, Manifest
        return Manifest(
            metadata=Metadata(
                name="dashboard",
                version="2.0.0",
                author="AstrumShell",
                description="WebUI 仪表盘"
            ),
            config=PluginConfig(enabled=True, args={}),
            dependencies=["http-api", "webui"]
        )

    def set_webui(self, webui):
        self.webui = webui

    def init(self, deps: dict = None):
        if self.webui:
            Log.info("dashboard", "已获取 WebUI 引用")
            self.webui.register_page(
                path='/dashboard',
                content_provider=self._render_content,
                nav_item={'icon': 'ri-dashboard-line', 'text': tr("dashboard.title", "系统仪表盘")}
            )
            if hasattr(self.webui, 'server') and self.webui.server:
                self.webui.server.router.get("/api/dashboard/stats", self._handle_stats_api)
                self.webui.server.router.get("/api/dashboard/history", self._handle_history_api)
                # 仪表盘自己的静态资源（与 WebUI 容器同源，无需额外端口）
                self.webui.server.router.get("/static/css/dashboard.css", self._handle_css)
                self.webui.server.router.get("/static/js/dashboard.js", self._handle_js)
            Log.info("dashboard", "已注册到 WebUI 导航")
        else:
            Log.warn("dashboard", "警告: 未找到 WebUI 依赖")

    def _static_path(self, kind: str, name: str) -> str:
        path = os.path.join(os.path.dirname(__file__), 'assets', kind, name)
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _handle_css(self, request):
        try:
            body = self._static_path('css', 'dashboard.css')
        except Exception as exc:
            return Response(status=404, headers={"Content-Type": "text/plain; charset=utf-8"}, body=str(exc))
        return Response(status=200, headers={"Content-Type": "text/css; charset=utf-8"}, body=body)

    def _handle_js(self, request):
        try:
            body = self._static_path('js', 'dashboard.js')
        except Exception as exc:
            return Response(status=404, headers={"Content-Type": "text/plain; charset=utf-8"}, body=str(exc))
        return Response(status=200, headers={"Content-Type": "application/javascript; charset=utf-8"}, body=body)


    def _get_uptime_str(self):
        """计算项目运行时间（从插件启动时算起）"""
        elapsed = time.time() - self._start_time
        days = int(elapsed // 86400)
        hours = int((elapsed % 86400) // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        if days > 0:
            return f"{days}天{hours}时{minutes}分{seconds}秒"
        elif hours > 0:
            return f"{hours}时{minutes}分{seconds}秒"
        elif minutes > 0:
            return f"{minutes}分{seconds}秒"
        else:
            return f"{seconds}秒"

    def _get_network_stats(self):
        try:
            net = psutil.net_io_counters()
            now = time.time()
            if self._last_net is None:
                self._last_net = (now, net.bytes_recv, net.bytes_sent)
                return {'recv_rate': 0, 'sent_rate': 0, 'total_recv': net.bytes_recv, 'total_sent': net.bytes_sent}
            elapsed = now - self._last_net[0]
            if elapsed <= 0: elapsed = 1
            recv_rate = (net.bytes_recv - self._last_net[1]) / elapsed
            sent_rate = (net.bytes_sent - self._last_net[2]) / elapsed
            self._last_net = (now, net.bytes_recv, net.bytes_sent)
            return {'recv_rate': round(recv_rate, 1), 'sent_rate': round(sent_rate, 1), 'total_recv': net.bytes_recv, 'total_sent': net.bytes_sent}
        except Exception as e:
            import traceback; print(f"[main.py] 错误:{type(e).__name__}:{e}"); traceback.print_exc()
            return {'recv_rate': 0, 'sent_rate': 0, 'total_recv': 0, 'total_sent': 0}

    def _get_disk_io_stats(self):
        try:
            disk_io = psutil.disk_io_counters()
            if not disk_io:
                return {'read_rate': 0, 'write_rate': 0}
            now = time.time()
            if self._last_disk is None:
                self._last_disk = (now, disk_io.read_bytes, disk_io.write_bytes)
                return {'read_rate': 0, 'write_rate': 0}
            elapsed = now - self._last_disk[0]
            if elapsed <= 0: elapsed = 1
            read_rate = (disk_io.read_bytes - self._last_disk[1]) / elapsed
            write_rate = (disk_io.write_bytes - self._last_disk[2]) / elapsed
            self._last_disk = (now, disk_io.read_bytes, disk_io.write_bytes)
            return {'read_rate': round(read_rate, 1), 'write_rate': round(write_rate, 1)}
        except Exception as e:
            import traceback; print(f"[main.py] 错误:{type(e).__name__}:{e}"); traceback.print_exc()
            return {'read_rate': 0, 'write_rate': 0}

    def _get_network_latency(self) -> float:
        """测量到公共 DNS 8.8.8.8 的 TCP 连接延迟（毫秒）

        连接有超时开销，因此由采样循环控制调用频率（每 LATENCY_EVERY 次测一次），
        其余时刻复用上一次结果；无外网时记 0，不刷 traceback。
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            start = time.time()
            s.connect(('8.8.8.8', 53))
            self._last_latency = round((time.time() - start) * 1000, 1)
            s.close()
        except Exception:
            self._last_latency = 0.0
        return self._last_latency

    def _get_network_interfaces(self):
        try:
            interfaces = []
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            for name, addr_list in addrs.items():
                if name == 'lo':
                    continue
                info = {'name': name, 'ip': 'N/A', 'mac': 'N/A', 'is_up': False, 'speed': 0}
                for addr in addr_list:
                    if addr.family == socket.AF_INET:
                        info['ip'] = addr.address
                    elif hasattr(psutil, 'AF_LINK') and addr.family == psutil.AF_LINK:
                        info['mac'] = addr.address
                if name in stats:
                    info['is_up'] = stats[name].isup
                    info['speed'] = stats[name].speed
                interfaces.append(info)
            return interfaces
        except Exception as e:
            import traceback; print(f"[main.py] 错误:{type(e).__name__}:{e}"); traceback.print_exc()
            return []

    def _get_load_info(self):
        try:
            load1, load5, load15 = os.getloadavg()
            return {'load1': round(load1, 2), 'load5': round(load5, 2), 'load15': round(load15, 2)}
        except (OSError, AttributeError):
            return {'load1': 0, 'load5': 0, 'load15': 0}

    # ========== 采样与 API ==========

    def _collect_stats(self, measure_latency: bool = True) -> dict:
        """采集一次系统指标：写入历史并更新缓存快照"""
        cpu_percent = psutil.cpu_percent(interval=None)     # 非阻塞：与上次调用的间隔有关
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = self._get_network_stats()
        disk_io = self._get_disk_io_stats()
        load = self._get_load_info()
        latency = self._get_network_latency() if measure_latency else self._last_latency

        with self._lock:
            self._cpu_history.append(round(cpu_percent, 1))
            self._ram_history.append(round(mem.percent, 1))
            self._net_recv_history.append(net['recv_rate'])
            self._net_sent_history.append(net['sent_rate'])
            self._disk_read_history.append(disk_io['read_rate'])
            self._disk_write_history.append(disk_io['write_rate'])
            self._net_latency_history.append(latency)
            self._sample_count += 1

        data = {
            'cpu': {'percent': round(cpu_percent, 1), 'cores': psutil.cpu_count(logical=True)},
            'ram': {'percent': round(mem.percent, 1), 'used': round(mem.used / (1024**3), 1),
                    'total': round(mem.total / (1024**3), 1)},
            'disk': {'percent': round(disk.percent, 1), 'used': round(disk.used / (1024**3), 1),
                     'total': round(disk.total / (1024**3), 1)},
            'network': net,
            'disk_io': disk_io,
            'load': load,
            'latency': latency,
            'processes': len(psutil.pids()),
            'uptime': self._get_uptime_str(),
            'sampled_at': time.time(),
            'host': {
                'os': f"{platform.system()} {platform.release()}",
                'python': platform.python_version(),
                'hostname': platform.node(),
            },
        }
        with self._lock:
            self._last_stats = data
        return data

    def _start_sampler(self):
        """启动后台采样线程（前端不打开时也在积累趋势数据）"""
        if self._sampler is not None and self._sampler.is_alive():
            return
        self._sampler_stop.clear()
        self._sampler = threading.Thread(target=self._sample_loop, name="dashboard-sampler", daemon=True)
        self._sampler.start()
        Log.info("dashboard", f"后台采样已启动（每 {self._sample_interval:.0f} 秒一次）")

    def _sample_loop(self):
        tick = 0
        while not self._sampler_stop.is_set():
            try:
                self._collect_stats(measure_latency=(tick % self.LATENCY_EVERY == 0))
            except Exception as exc:
                Log.warn("dashboard", f"采样失败：{type(exc).__name__}: {exc}")
            tick += 1
            self._sampler_stop.wait(self._sample_interval)

    def _stop_sampler(self):
        self._sampler_stop.set()
        sampler, self._sampler = self._sampler, None
        if sampler is not None:
            sampler.join(timeout=3)

    def _handle_stats_api(self, request):
        """当前指标：直接返回采样线程的缓存（毫秒级，不再阻塞 0.3 秒）"""
        try:
            with self._lock:
                data = dict(self._last_stats)
            if not data:
                data = self._collect_stats(measure_latency=False)
            data['interval'] = self._sample_interval
            with self._lock:
                data['samples'] = self._sample_count
                data['history_len'] = self._history_len
            return Response(status=200, headers={"Content-Type": "application/json"}, body=json.dumps(data))
        except Exception as e:
            return Response(status=500, headers={"Content-Type": "application/json"}, body=json.dumps({'error': str(e)}))

    def _handle_history_api(self, request):
        """历史趋势：CPU / 内存 / 网络 / 磁盘 IO / 延迟"""
        try:
            with self._lock:
                data = {
                    'cpu': list(self._cpu_history),
                    'ram': list(self._ram_history),
                    'net_recv': list(self._net_recv_history),
                    'net_sent': list(self._net_sent_history),
                    'disk_read': list(self._disk_read_history),
                    'disk_write': list(self._disk_write_history),
                    'latency': list(self._net_latency_history),
                    'samples': self._sample_count,
                    'interval': self._sample_interval,
                    'max_len': self._history_len,
                }
            return Response(status=200, headers={"Content-Type": "application/json"}, body=json.dumps(data))
        except Exception as e:
            return Response(status=500, headers={"Content-Type": "application/json"}, body=json.dumps({'error': str(e)}))

    def start(self):
        self._start_sampler()
        Log.info("dashboard", "仪表盘已启动")

    def stop(self):
        self._stop_sampler()
        Log.info("dashboard", "仪表盘已停止")

    def _default_interval(self):
        """默认刷新间隔（秒，0 表示不自动刷新）：优先读 WebUI 设置"""
        try:
            settings = self.webui.get_settings() if self.webui is not None else {}
            if settings.get("dashboard_auto_refresh") is False:
                return 0
            value = float(settings.get("dashboard_refresh_interval", 2))
            return min(max(value, 1.0), 60.0)
        except Exception:
            return 2.0

    def _render_content(self) -> str:
        """渲染仪表盘**片段**（注入 WebUI 布局）

        页面只负责骨架，所有数字/图表由 /api/dashboard/stats 与 /history 实时拉取，
        不再整页 reload。
        """
        labels = {
            "title": tr("dashboard.title", "系统仪表盘"),
            "cpu": tr("dashboard.cpu", "CPU 使用率"),
            "ram": tr("dashboard.ram", "内存使用"),
            "disk": tr("dashboard.disk", "磁盘使用"),
            "network": tr("dashboard.network", "网络吞吐"),
            "recv": tr("dashboard.recv", "下载"),
            "sent": tr("dashboard.sent", "上传"),
            "disk_io": tr("dashboard.disk_io", "磁盘 IO"),
            "read": tr("dashboard.read", "读取"),
            "write": tr("dashboard.write", "写入"),
            "latency": tr("dashboard.latency", "网络延迟"),
            "processes": tr("dashboard.processes", "进程数"),
            "uptime": tr("dashboard.uptime", "运行时间"),
            "os": tr("dashboard.os", "操作系统"),
            "python": tr("dashboard.python", "Python 版本"),
            "hostname": tr("dashboard.hostname", "主机名"),
            "load": "Load",
            "pause": tr("dashboard.pause", "暂停刷新"),
            "resume": tr("dashboard.resume", "继续刷新"),
            "refresh_now": tr("dashboard.refresh_now", "立即刷新"),
            "last_update": tr("dashboard.last_update", "最后更新"),
            "never": tr("dashboard.never", "等待首次采样"),
            "auto": tr("dashboard.auto", "自动刷新"),
            "paused": tr("dashboard.paused", "已暂停"),
            "error": tr("dashboard.error", "数据获取失败"),
            "trend": tr("dashboard.trend", "最近 {{count}} 个采样点"),
            "live": tr("dashboard.live", "实时"),
            "offline": tr("dashboard.offline", "离线"),
            "seconds": tr("webui.seconds", "秒"),
            "cores": tr("dashboard.cores", "{{count}} 核心"),
        }
        interval = self._default_interval()
        payload = json.dumps(
            {"labels": labels, "interval": interval},
            ensure_ascii=False,
        ).replace("</", "<\\/")

        def gauge(key: str) -> str:
            return f"""
                <div class="gauge-card">
                    <div class="gauge-container">
                        <svg class="gauge-svg" width="120" height="120" viewBox="0 0 120 120">
                            <circle class="gauge-bg" cx="60" cy="60" r="52"></circle>
                            <circle class="gauge-fill" id="gauge-{key}" cx="60" cy="60" r="52"
                                    stroke-dasharray="326.7" stroke-dashoffset="326.7"></circle>
                        </svg>
                        <div class="gauge-text" id="gauge-{key}-text">--%</div>
                    </div>
                    <div class="gauge-label">{labels[key]}</div>
                    <div class="gauge-extra" id="gauge-{key}-extra"></div>
                </div>"""

        def chart(key: str, label_key: str) -> str:
            return f"""
                <div class="chart">
                    <div class="chart-head">
                        <span class="chart-label">{labels[label_key]}</span>
                        <span class="chart-val" id="chart-{key}-val">—</span>
                    </div>
                    <canvas id="chart-{key}" height="64"></canvas>
                </div>"""

        info_rows = "".join(
            f'<div class="field"><span class="field-key">{label}</span>'
            f'<span class="field-val" id="info-{key}">—</span></div>'
            for key, label in (
                ("uptime", labels["uptime"]),
                ("os", labels["os"]),
                ("python", labels["python"]),
                ("hostname", labels["hostname"]),
                ("processes", labels["processes"]),
                ("load", labels["load"]),
            )
        )

        return f"""
<link rel="stylesheet" href="/static/css/dashboard.css">
<div class="page dashboard-page">
    <header class="page-head">
        <h1><i class="ri-dashboard-line"></i> {labels['title']}</h1>
        <p class="page-sub">
            <span id="dash-state" class="dash-state">…</span>
            <span class="dash-sep">·</span>
            <span id="dash-last">{labels['last_update']}: {labels['never']}</span>
        </p>
    </header>

    <section class="dash-gauges">{gauge('cpu')}{gauge('ram')}{gauge('disk')}</section>

    <div class="actions">
        <button type="button" id="dash-toggle" class="btn">{labels['pause']}</button>
        <button type="button" id="dash-refresh" class="btn btn-primary">{labels['refresh_now']}</button>
        <label class="dash-interval">{labels['auto']}
            <select id="dash-interval" class="input">
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="5">5</option>
                <option value="10">10</option>
                <option value="30">30</option>
            </select>
            <span class="hint">{labels['seconds']}</span>
        </label>
    </div>

    <section class="panel">
        <h2>{labels['trend']} <span class="hint" id="dash-window"></span></h2>
        <div class="charts">
            {chart('cpu', 'cpu')}
            {chart('ram', 'ram')}
            {chart('net', 'network')}
            {chart('diskio', 'disk_io')}
            {chart('latency', 'latency')}
        </div>
    </section>

    <section class="panel">
        <h2>{labels['title']}</h2>
        <div class="kv">{info_rows}</div>
    </section>
</div>
<script id="dashboard-data" type="application/json">{payload}</script>
<script src="/static/js/dashboard.js" defer></script>
"""


register_plugin_type("DashboardPlugin", DashboardPlugin)


def New():
    return DashboardPlugin()
