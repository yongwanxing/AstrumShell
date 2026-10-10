"""TCP HTTP 路由器"""
from typing import Callable, Optional, Any
from oss.shared.router import BaseRouter, match_path


class TcpRouter(BaseRouter):
    """TCP HTTP 路由器"""

    def handle(self, request: dict) -> dict:
        """处理请求"""
        method = request.get("method", "GET")
        path = request.get("path", "/")
        
        result = self.find_route(method, path)
        if result:
            route, params = result
            # 将路径参数注入到请求中
            request["path_params"] = params
            return route.handler(request)

        return {"status": 404, "headers": {}, "body": "Not Found"}
