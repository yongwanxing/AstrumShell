"""插件桥接器 - 共享事件、广播、桥接"""
from typing import Any, Callable, Optional
from dataclasses import dataclass, field

from oss.logger.logger import Log
from oss.plugin.types import Plugin, register_plugin_type


@dataclass
class BridgeEvent:
    """桥接事件"""
    type: str
    source_plugin: str
    payload: Any = None
    context: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """事件总线"""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
        self._history: list[BridgeEvent] = []

    def emit(self, event: BridgeEvent):
        """发布事件"""
        self._history.append(event)
        handlers = self._handlers.get(event.type, [])
        wildcard_handlers = self._handlers.get("*", [])
        for handler in handlers + wildcard_handlers:
            try:
                handler(event)
            except Exception as e:
                import traceback; print(f"[main.py] 错误:{type(e).__name__}:{e}"); traceback.print_exc()
                pass

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

    def once(self, event_type: str, handler: Callable):
        """仅触发一次"""
        def wrapper(event):
            self.off(event_type, wrapper)
            handler(event)
        self.on(event_type, wrapper)

    def get_history(self, event_type: str = None) -> list[BridgeEvent]:
        """获取事件历史"""
        if event_type:
            return [e for e in self._history if e.type == event_type]
        return self._history.copy()

    def clear_history(self):
        """清空事件历史"""
        self._history.clear()


class BroadcastManager:
    """广播管理器"""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._channels: dict[str, list[str]] = {}

    def create_channel(self, name: str, plugins: list[str]):
        """创建广播频道"""
        self._channels[name] = plugins

    def broadcast(self, channel: str, payload: Any, source_plugin: str = ""):
        """广播到指定频道"""
        if channel not in self._channels:
            return
        event = BridgeEvent(
            type=f"broadcast.{channel}",
            source_plugin=source_plugin,
            payload=payload
        )
        self.event_bus.emit(event)

    def get_channels(self) -> dict[str, list[str]]:
        """获取所有频道"""
        return self._channels.copy()


class ServiceRegistry:
    """服务注册表（RPC）"""

    def __init__(self):
        self._services: dict[str, dict[str, Callable]] = {}

    def register(self, plugin_name: str, service_name: str, handler: Callable):
        """注册服务"""
        if plugin_name not in self._services:
            self._services[plugin_name] = {}
        self._services[plugin_name][service_name] = handler

    def unregister(self, plugin_name: str, service_name: str = None):
        """注销服务"""
        if plugin_name in self._services:
            if service_name:
                self._services[plugin_name].pop(service_name, None)
            else:
                del self._services[plugin_name]

    def call(self, plugin_name: str, service_name: str, *args, **kwargs) -> Any:
        """远程调用"""
        if plugin_name not in self._services:
            raise RuntimeError(f"插件 '{plugin_name}' 未注册服务")
        if service_name not in self._services[plugin_name]:
            raise RuntimeError(f"插件 '{plugin_name}' 未注册服务 '{service_name}'")
        return self._services[plugin_name][service_name](*args, **kwargs)

    def list_services(self, plugin_name: str = None) -> dict[str, dict[str, Callable]]:
        """列出服务"""
        if plugin_name:
            return self._services.get(plugin_name, {}).copy()
        return {k: v.copy() for k, v in self._services.items()}


class BridgeManager:
    """桥接管理器"""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._bridges: dict[str, dict[str, Any]] = {}

    def create_bridge(self, name: str, from_plugin: str, to_plugin: str, event_mapping: dict[str, str]):
        """创建桥接：将 from_plugin 的事件映射到 to_plugin"""
        self._bridges[name] = {
            "from": from_plugin,
            "to": to_plugin,
            "mapping": event_mapping,
        }
        # 注册桥接处理器
        for src_event, dst_event in event_mapping.items():
            def handler(event, dst_event=dst_event):
                bridged = BridgeEvent(
                    type=dst_event,
                    source_plugin=event.source_plugin,
                    payload=event.payload,
                    context={**event.context, "_bridged_from": event.type}
                )
                self.event_bus.emit(bridged)
            self.event_bus.on(src_event, handler)

    def remove_bridge(self, name: str):
        """移除桥接"""
        if name in self._bridges:
            del self._bridges[name]

    def get_bridges(self) -> dict[str, dict[str, Any]]:
        """获取所有桥接"""
        return self._bridges.copy()


class PluginBridgePlugin(Plugin):
    """插件桥接器插件"""

    def __init__(self):
        self.event_bus = EventBus()
        self.broadcast = None
        self.bridge = None
        self.services = ServiceRegistry()
        self.storage = None  # 共享存储接口

    def init(self, deps: dict = None):
        """初始化"""
        self.broadcast = BroadcastManager(self.event_bus)
        self.bridge = BridgeManager(self.event_bus)

    def start(self):
        """启动"""
        Log.info("plugin-bridge", "事件总线、广播、桥接、RPC、共享存储已启动")

    def stop(self):
        """停止"""
        self.event_bus.clear_history()

    def set_plugin_storage(self, storage_plugin):
        """设置存储插件引用"""
        if storage_plugin:
            self.storage = storage_plugin.get_shared()


# 注册类型
register_plugin_type("BridgeEvent", BridgeEvent)
register_plugin_type("EventBus", EventBus)
register_plugin_type("BroadcastManager", BroadcastManager)
register_plugin_type("BridgeManager", BridgeManager)
register_plugin_type("ServiceRegistry", ServiceRegistry)


def New():
    return PluginBridgePlugin()
