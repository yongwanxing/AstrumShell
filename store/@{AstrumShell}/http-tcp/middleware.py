"""TCP HTTP 中间件链"""
from typing import Callable, Optional, Any


class TcpMiddleware:
    """TCP 中间件基类"""
    def process(self, request: dict, next_fn: Callable) -> Optional[dict]:
        """处理请求"""
        return next_fn()


class TcpLogMiddleware(TcpMiddleware):
    """日志中间件"""
    def process(self, request, next_fn):
        print(f"[http-tcp] {request.get('method')} {request.get('path')}")
        return next_fn()


class TcpCorsMiddleware(TcpMiddleware):
    """CORS 中间件"""
    def process(self, request, next_fn):
        response = next_fn()
        if response:
            response.setdefault("headers", {})
            response["headers"]["Access-Control-Allow-Origin"] = "*"
        return response


class TcpMiddlewareChain:
    """TCP 中间件链"""

    def __init__(self):
        self.middlewares: list[TcpMiddleware] = []
        self.add(TcpLogMiddleware())
        self.add(TcpCorsMiddleware())

    def add(self, middleware: TcpMiddleware):
        """添加中间件"""
        self.middlewares.append(middleware)

    def run(self, request: dict) -> Optional[dict]:
        """执行中间件链"""
        idx = 0

        def next_fn():
            nonlocal idx
            if idx < len(self.middlewares):
                mw = self.middlewares[idx]
                idx += 1
                return mw.process(request, next_fn)
            return None

        return next_fn()
