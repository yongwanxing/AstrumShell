"""HTTP TCP 事件定义"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TcpEvent:
    """TCP 事件"""
    type: str
    client: Any = None
    data: bytes = b""
    context: dict[str, Any] = field(default_factory=dict)


# 事件类型常量
EVENT_CONNECT = "tcp.connect"
EVENT_DISCONNECT = "tcp.disconnect"
EVENT_DATA = "tcp.data"
EVENT_REQUEST = "tcp.http.request"
EVENT_RESPONSE = "tcp.http.response"
EVENT_ERROR = "tcp.error"
