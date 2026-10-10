"""插件加载 Pro - 为 plugin-loader 提供高级机制"""
from oss.plugin.types import Plugin, register_plugin_type
from .core.config import ProConfig
from .core.enhancer import PluginLoaderEnhancer
from .utils.logger import ProLogger


class PluginLoaderPro(Plugin):
    """插件加载 Pro - 增强器"""

    def __init__(self):
        self.plugin_loader = None
        self.enhancer = None
        self.config = None
        self._started = False

    def meta(self):
        from oss.plugin.types import Metadata, PluginConfig, Manifest
        return Manifest(
            metadata=Metadata(
                name="plugin-loader-pro",
                version="1.0.0",
                author="AstrumShell",
                description="为 plugin-loader 提供熔断、降级、容错、自动修复等高级机制"
            ),
            config=PluginConfig(
                enabled=True,
                args={}
            ),
            dependencies=["plugin-loader"]
        )

    def set_plugin_loader(self, plugin_loader):
        self.plugin_loader = plugin_loader
        ProLogger.info("main", "已注入 plugin-loader")

    def init(self, deps: dict = None):
        if not self.plugin_loader:
            ProLogger.warn("main", "未找到 plugin-loader 依赖")
            return

        config = {}
        if deps:
            config = deps.get("config", {})

        self.config = ProConfig(config)
        self.enhancer = PluginLoaderEnhancer(
            self.plugin_loader.manager,
            self.config
        )

        ProLogger.info("main", "增强器已初始化")

    def start(self):
        if self._started:
            return
        self._started = True

        if not self.enhancer:
            ProLogger.warn("main", "增强器未初始化，跳过启动")
            return

        ProLogger.info("main", "开始增强 plugin-loader...")
        self.enhancer.enhance()

    def stop(self):
        ProLogger.info("main", "停止增强器...")
        if self.enhancer:
            self.enhancer.disable()


register_plugin_type("PluginLoaderPro", PluginLoaderPro)


def New():
    return PluginLoaderPro()
