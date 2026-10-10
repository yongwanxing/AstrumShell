"""重试处理器"""
import time
import random
from typing import Callable, Any
from ..core.config import RetryConfig
from ..utils.logger import ProLogger


class RetryHandler:
    """重试处理器"""

    def __init__(self, config: RetryConfig = None):
        config = config or RetryConfig()
        self.max_retries = config.max_retries
        self.backoff_factor = config.backoff_factor
        self.initial_delay = config.initial_delay

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """执行带重试的调用"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    ProLogger.warn("retry", f"第 {attempt + 1} 次重试，等待 {delay:.1f}s: {e}")
                    time.sleep(delay)

        raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """计算退避延迟"""
        delay = self.initial_delay * (self.backoff_factor ** attempt)
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter
