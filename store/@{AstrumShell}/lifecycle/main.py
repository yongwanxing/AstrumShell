"""生命周期插件 - 管理插件生命周期状态"""
from enum import Enum
from typing import Optional, Callable, Any

from oss.plugin.types import Plugin, register_plugin_type


class LifecycleState(str, Enum):
    """生命周期状态"""
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"


class LifecycleError(Exception):
    """生命周期错误"""
    pass


class Lifecycle:
    """生命周期管理器"""

    VALID_TRANSITIONS = {
        LifecycleState.PENDING: [LifecycleState.RUNNING],
        LifecycleState.RUNNING: [LifecycleState.STOPPED],
        LifecycleState.STOPPED: [LifecycleState.RUNNING],
    }

    def __init__(self, name: str):
        self.name = name
        self.state = LifecycleState.PENDING
        self._hooks: dict[str, list[Callable]] = {
            "before_start": [],
            "after_start": [],
            "before_stop": [],
            "after_stop": [],
        }
        self._extensions: dict[str, Any] = {}  # 扩展能力

    def add_extension(self, name: str, extension: Any):
        """添加扩展能力"""
        self._extensions[name] = extension

    def get_extension(self, name: str) -> Optional[Any]:
        """获取扩展能力"""
        return self._extensions.get(name)

    def transition(self, target_state: LifecycleState):
        """状态转换"""
        if target_state not in self.VALID_TRANSITIONS.get(self.state, []):
            raise LifecycleError(
                f"插件 '{self.name}' 无法从 {self.state.value} 转换到 {target_state.value}"
            )

        old_state = self.state
        self.state = target_state

    def start(self):
        """启动"""
        for hook in self._hooks["before_start"]:
            hook(self)
        self.transition(LifecycleState.RUNNING)
        for hook in self._hooks["after_start"]:
            hook(self)

    def stop(self):
        """停止"""
        for hook in self._hooks["before_stop"]:
            hook(self)
        self.transition(LifecycleState.STOPPED)
        for hook in self._hooks["after_stop"]:
            hook(self)

    def restart(self):
        """重启"""
        if self.state == LifecycleState.RUNNING:
            self.stop()
        self.start()

    def on(self, event: str, hook: Callable):
        """注册钩子"""
        if event in self._hooks:
            self._hooks[event].append(hook)

    def is_running(self) -> bool:
        return self.state == LifecycleState.RUNNING

    def is_stopped(self) -> bool:
        return self.state == LifecycleState.STOPPED

    def is_pending(self) -> bool:
        return self.state == LifecycleState.PENDING

    def __repr__(self):
        return f"Lifecycle({self.name}, state={self.state.value})"


class LifecyclePlugin(Plugin):
    """生命周期插件"""

    def __init__(self):
        self.lifecycles: dict[str, Lifecycle] = {}

    def init(self, deps: dict = None):
        """初始化"""
        pass

    def start(self):
        """启动"""
        pass

    def stop(self):
        """停止"""
        pass

    def create(self, name: str) -> Lifecycle:
        """创建生命周期"""
        lifecycle = Lifecycle(name)
        self.lifecycles[name] = lifecycle
        return lifecycle

    def get(self, name: str) -> Optional[Lifecycle]:
        """获取生命周期"""
        return self.lifecycles.get(name)

    def start_all(self):
        """启动所有"""
        for lc in self.lifecycles.values():
            try:
                lc.start()
            except LifecycleError:
                pass

    def stop_all(self):
        """停止所有"""
        for lc in self.lifecycles.values():
            try:
                lc.stop()
            except LifecycleError:
                pass


# 注册类型
register_plugin_type("Lifecycle", Lifecycle)
register_plugin_type("LifecycleState", LifecycleState)
register_plugin_type("LifecycleError", LifecycleError)


def New():
    return LifecyclePlugin()
