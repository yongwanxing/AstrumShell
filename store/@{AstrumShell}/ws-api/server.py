"""WebSocket 服务器核心"""
import asyncio
import websockets
import threading
import json
from typing import Any, Callable, Optional
from .events import WsEvent, EVENT_CONNECT, EVENT_DISCONNECT, EVENT_MESSAGE


class WsClient:
    """WebSocket 客户端连接"""

    def __init__(self, websocket, path: str):
        self.websocket = websocket
        self.path = path
        self.id = id(websocket)
        self.closed = False

    async def send(self, message: Any):
        """发送消息"""
        if not self.closed:
            data = json.dumps(message, ensure_ascii=False) if isinstance(message, dict) else str(message)
            await self.websocket.send(data)

    async def close(self):
        """关闭连接"""
        self.closed = True
        await self.websocket.close()


class WsServer:
    """WebSocket 服务器"""

    def __init__(self, router, middleware, event_bus, host="0.0.0.0", port=8081):
        self.host = host
        self.port = port
        self.router = router
        self.middleware = middleware
        self.event_bus = event_bus
        self._server = None
        self._loop = None
        self._thread = None
        self._clients: dict[int, WsClient] = {}

    def start(self):
        """启动服务器"""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        """运行事件循环"""
        asyncio.set_event_loop(self._loop)
        start_server = websockets.serve(
            self._handle_connection,
            self.host,
            self.port
        )
        self._loop.run_until_complete(start_server)
        self._loop.run_forever()

    async def _handle_connection(self, websocket, path=None):
        """处理客户端连接（兼容 websockets 新旧版本）"""
        # websockets 16.0+ 只传入 connection 参数
        if path is None:
            # 新版本：从 websocket.request 获取路径
            try:
                path = websocket.request.path
            except AttributeError:
                path = "/"
        
        client = WsClient(websocket, path)
        self._clients[client.id] = client

        # 触发连接事件
        self.event_bus.emit(WsEvent(
            type=EVENT_CONNECT,
            client=client,
            path=path
        ))

        try:
            async for message in websocket:
                # 触发消息事件
                self.event_bus.emit(WsEvent(
                    type=EVENT_MESSAGE,
                    client=client,
                    path=path,
                    message=message
                ))

                # 路由处理
                await self.router.handle(client, path, message)

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            del self._clients[client.id]
            # 触发断开事件
            self.event_bus.emit(WsEvent(
                type=EVENT_DISCONNECT,
                client=client,
                path=path
            ))

    def stop(self):
        """停止服务器"""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        print("[ws-api] 服务器已停止")

    def broadcast(self, message: Any, exclude_client: int = None):
        """广播消息"""
        async def _broadcast():
            for client_id, client in self._clients.items():
                if exclude_client and client_id == exclude_client:
                    continue
                await client.send(message)
        
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(_broadcast(), self._loop)

    def get_clients(self) -> list[WsClient]:
        """获取所有客户端"""
        return list(self._clients.values())
