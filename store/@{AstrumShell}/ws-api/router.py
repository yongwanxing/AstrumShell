"""WebSocket 路由器"""
import json
import asyncio
from typing import Callable, Optional, Any
from .server import WsClient


class WsRoute:
    """WebSocket 路由"""
    def __init__(self, path: str, handler: Callable):
        self.path = path
        self.handler = handler


class WsRouter:
    """WebSocket 路由器"""

    def __init__(self):
        self.routes: dict[str, WsRoute] = {}

    def on_message(self, path: str, handler: Callable):
        """注册消息路由"""
        self.routes[path] = WsRoute(path, handler)

    async def handle(self, client: WsClient, path: str, message: str):
        """处理消息"""
        # 精确匹配
        if path in self.routes:
            await self.routes[path].handler(client, message)
            return

        # 前缀匹配
        for route_path, route in self.routes.items():
            if path.startswith(route_path):
                await route.handler(client, message)
                return

        # 无匹配路由
        await client.send({"error": "No handler for path", "path": path})
