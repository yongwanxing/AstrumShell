"""代码审查器插件"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from oss.logger.logger import Log
from oss.plugin.types import Plugin, register_plugin_type
from core.reviewer import CodeReviewer


class CodeReviewerPlugin(Plugin):
    """代码审查器插件"""

    def __init__(self):
        self.reviewer = None
        self.config = {}

    def meta(self):
        from oss.plugin.types import Metadata, PluginConfig, Manifest
        return Manifest(
            metadata=Metadata(
                name="code-reviewer",
                version="1.0.0",
                author="AstrumShell",
                description="代码审查器 - 自动扫描代码问题"
            ),
            config=PluginConfig(
                enabled=True,
                args={
                    "scan_dirs": ["store", "oss"],
                    "exclude_patterns": ["__pycache__", "*.pyc"],
                    "max_file_size": 102400,
                    "report_format": "console"
                }
            ),
            dependencies=[]
        )

    def init(self, deps: dict = None):
        config = {}
        if deps:
            config = deps.get("config", {})

        self.config = {
            "scan_dirs": config.get("scan_dirs", ["store", "oss"]),
            "exclude_patterns": config.get("exclude_patterns", ["__pycache__"]),
            "max_file_size": config.get("max_file_size", 102400),
            "report_format": config.get("report_format", "console")
        }

        self.reviewer = CodeReviewer(self.config)
        Log.info("code-reviewer", "初始化完成")

    def start(self):
        Log.info("code-reviewer", "插件已启动")

    def stop(self):
        Log.error("code-reviewer", "插件已停止")

    def check(self, dirs: list = None) -> dict:
        """执行代码检查"""
        scan_dirs = dirs or self.config["scan_dirs"]
        return self.reviewer.run_check(scan_dirs)


register_plugin_type("CodeReviewerPlugin", CodeReviewerPlugin)


def New():
    return CodeReviewerPlugin()
