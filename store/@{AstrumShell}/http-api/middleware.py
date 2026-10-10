"""中间件链 - CORS/日志/限流等"""
from typing import Callable, Optional, Any
from .server import Request, Response


class Middleware:
    """中间件基类"""
    def process(self, ctx: dict[str, Any], next_fn: Callable) -> Optional[Response]:
        """处理请求"""
        return None


class CorsMiddleware(Middleware):
    """CORS 中间件"""
    def process(self, ctx: dict, next_fn: Callable) -> Optional[Response]:
        ctx["response_headers"] = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        return None


class LoggerMiddleware(Middleware):
    """日志中间件"""
    # 静默的路由（不打印日志）
    _silent_paths = {"/api/dashboard/stats", "/favicon.ico", "/health"}
    
    def process(self, ctx: dict, next_fn: Callable) -> Optional[Response]:
        req = ctx.get("request")
        if req and req.path not in self._silent_paths:
            print(f"[http-api] {req.method} {req.path}")
        return None


class MiddlewareChain:
    """中间件链"""

    def __init__(self):
        self.middlewares: list[Middleware] = []
        self.add(LoggerMiddleware())
        self.add(CorsMiddleware())

    def add(self, middleware: Middleware):
        """添加中间件"""
        self.middlewares.append(middleware)

    def run(self, ctx: dict[str, Any]) -> Optional[Response]:
        """执行中间件链"""
        idx = 0

        def next_fn():
            nonlocal idx
            if idx < len(self.middlewares):
                mw = self.middlewares[idx]
                idx += 1
                return mw.process(ctx, next_fn)
            return None

        return next_fn()
