"""健康检查器"""
import time
import threading
from typing import Any
from ..utils.logger import ProLogger


class HealthChecker:
    """健康检查器"""

    def __init__(self, interval: int = 30, timeout: int = 5, max_failures: int = 5):
        self.interval = interval
        self.timeout = timeout
        self.max_failures = max_failures

        self._running = False
        self._thread = None
        self._plugins: dict[str, Any] = {}
        self._failure_counts: dict[str, int] = {}
        self._on_failure_callback = None

    def add_plugin(self, name: str, instance: Any):
        """添加要监控的插件"""
        self._plugins[name] = instance
        self._failure_counts[name] = 0

    def start(self, on_failure_callback=None):
        """启动健康检查"""
        self._on_failure_callback = on_failure_callback
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        ProLogger.info("health", "健康检查已启动")

    def stop(self):
        """停止健康检查"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _check_loop(self):
        """检查循环"""
        while self._running:
            for name, instance in self._plugins.items():
                self._check_plugin(name, instance)
            time.sleep(self.interval)

    def _check_plugin(self, name: str, instance: Any):
        """检查单个插件"""
        try:
            if hasattr(instance, 'health'):
                healthy = instance.health()
                if not healthy:
                    self._on_failure(name)
            else:
                self._failure_counts[name] = 0
        except Exception as e:
            ProLogger.error("health", f"插件 {name} 健康检查失败: {type(e).__name__}: {e}")
            self._on_failure(name)

    def _on_failure(self, name: str):
        """失败处理"""
        self._failure_counts[name] = self._failure_counts.get(name, 0) + 1

        if self._failure_counts[name] >= self.max_failures:
            ProLogger.warn("health", f"插件 {name} 连续失败 {self._failure_counts[name]} 次")
            if self._on_failure_callback:
                self._on_failure_callback(name)

    def reset_failure_count(self, name: str):
        """重置失败计数"""
        self._failure_counts[name] = 0

    def get_failure_count(self, name: str) -> int:
        """获取失败计数"""
        return self._failure_counts.get(name, 0)
