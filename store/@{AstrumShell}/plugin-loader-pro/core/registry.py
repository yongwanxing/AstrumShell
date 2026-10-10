"""能力注册表"""
from typing import Any, Optional
from .proxy import PermissionError


class CapabilityRegistry:
    """能力注册表"""

    def __init__(self, permission_check: bool = True):
        self.providers: dict[str, dict[str, Any]] = {}
        self.consumers: dict[str, list[str]] = {}
        self.permission_check = permission_check

    def register_provider(self, capability: str, plugin_name: str, instance: Any):
        """注册能力提供者"""
        self.providers[capability] = {
            "plugin": plugin_name,
            "instance": instance,
        }
        if capability not in self.consumers:
            self.consumers[capability] = []

    def register_consumer(self, capability: str, plugin_name: str):
        """注册能力消费者"""
        if capability not in self.consumers:
            self.consumers[capability] = []
        if plugin_name not in self.consumers[capability]:
            self.consumers[capability].append(plugin_name)

    def get_provider(self, capability: str, requester: str = "",
                     allowed_plugins: list[str] = None) -> Optional[Any]:
        """获取能力提供者实例（带权限检查）"""
        if capability not in self.providers:
            return None

        if self.permission_check and allowed_plugins is not None:
            provider_name = self.providers[capability]["plugin"]
            if (provider_name != requester and
                    provider_name not in allowed_plugins and
                    "*" not in allowed_plugins):
                raise PermissionError(
                    f"插件 '{requester}' 无权使用能力 '{capability}'"
                )

        return self.providers[capability]["instance"]

    def has_capability(self, capability: str) -> bool:
        return capability in self.providers

    def get_consumers(self, capability: str) -> list[str]:
        return self.consumers.get(capability, [])
