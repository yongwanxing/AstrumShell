"""路由器 - 路径匹配和处理器分发"""
from typing import Callable, Optional
from oss.shared.router import BaseRouter, match_path
from .server import Request, Response


class Router(BaseRouter):
    """HTTP API 路由器"""

    def handle(self, request: Request) -> Response:
        """处理请求"""
        # 匹配时忽略查询串：/api/x?y=1 应命中 /api/x
        # （request.path 保留原值，处理器仍可自行解析查询参数）
        path = request.path.split("?", 1)[0]
        result = self.find_route(request.method, path)
        if result:
            route, params = result
            # 将路径参数注入到请求中
            request.path_params = params
            return route.handler(request)
        return Response(status=404, body='{"error": "Not Found"}')
