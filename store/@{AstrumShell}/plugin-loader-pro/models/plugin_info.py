"""插件信息模型"""
from typing import Any


class PluginInfo:
    """插件信息"""
    def __init__(self):
        self.name: str = ""
        self.version: str = ""
        self.author: str = ""
        self.description: str = ""
        self.readme: str = ""
        self.config: dict[str, Any] = {}
        self.extensions: dict[str, Any] = {}
        self.lifecycle: Any = None
        self.capabilities: set[str] = set()
        self.dependencies: list[str] = []
        self.status: str = "idle"  # idle, running, stopped, error
        self.error_count: int = 0
        self.last_error: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "status": self.status,
            "error_count": self.error_count
        }
