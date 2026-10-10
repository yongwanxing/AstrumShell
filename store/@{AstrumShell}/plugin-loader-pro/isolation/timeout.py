"""超时控制"""
import signal


class TimeoutError(Exception):
    """超时错误"""
    pass


class TimeoutController:
    """超时控制器"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def execute_with_timeout(self, func, *args, **kwargs) -> any:
        """在超时限制内执行函数"""
        def handler(signum, frame):
            raise TimeoutError(f"执行超时 (>{self.timeout}s)")

        old_handler = signal.signal(signal.SIGALRM, handler)
        signal.alarm(self.timeout)

        try:
            result = func(*args, **kwargs)
            signal.alarm(0)
            return result
        finally:
            signal.signal(signal.SIGALRM, old_handler)
