"""WebSocket 事件定义"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class WsEvent:
    """WebSocket 事件"""
    type: str
    client: Any = None
    path: str = ""
    message: str = ""
    context: dict[str, Any] = field(default_factory=dict)


# 事件类型常量
EVENT_CONNECT = "ws.connect"
EVENT_DISCONNECT = "ws.disconnect"
EVENT_MESSAGE = "ws.message"
EVENT_ERROR = "ws.error"
EVENT_SUBSCRIBE = "ws.subscribe"
EVENT_UNSUBSCRIBE = "ws.unsubscribe"
EVENT_BROADCAST = "ws.broadcast"
