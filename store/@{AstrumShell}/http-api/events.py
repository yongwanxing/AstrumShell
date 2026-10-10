"""HTTP 事件系统 - 请求/响应生命周期事件"""
from typing import Callable, Any, Optional
from dataclasses import dataclass, field


@dataclass
class HttpEvent:
    """HTTP 事件"""
    type: str  # request, response, error, etc
    request: Any = None
    response: Any = None
    error: Exception = None
    context: dict[str, Any] = field(default_factory=dict)


class HttpEventBus:
    """HTTP 事件总线"""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}

    def on(self, event_type: str, handler: Callable):
        """订阅事件"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def off(self, event_type: str, handler: Callable):
        """取消订阅"""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    def emit(self, event: HttpEvent):
        """发布事件"""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                import traceback; print(f"[events.py] 错误:{type(e).__name__}:{e}"); traceback.print_exc()
                pass

    def clear(self):
        """清空所有订阅"""
        self._handlers.clear()


# 事件类型常量
EVENT_REQUEST = "http.request"
EVENT_BEFORE_ROUTE = "http.before_route"
EVENT_AFTER_ROUTE = "http.after_route"
EVENT_BEFORE_HANDLER = "http.before_handler"
EVENT_AFTER_HANDLER = "http.after_handler"
EVENT_RESPONSE = "http.response"
EVENT_ERROR = "http.error"
EVENT_COMPLETE = "http.complete"
