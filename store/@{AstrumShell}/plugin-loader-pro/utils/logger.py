"""插件加载 Pro - 日志工具"""
import sys


class ProLogger:
    """Pro 日志记录器 - 智能颜色识别"""

    _COLORS = {
        "reset": "\033[0m",
        "white": "\033[0;37m",
        "yellow": "\033[1;33m",
        "blue": "\033[1;34m",
        "red": "\033[1;31m",
    }

    @staticmethod
    def _colorize(text: str, color: str) -> str:
        """添加颜色（终端支持时）"""
        if not sys.stdout.isatty():
            return text
        return f"{ProLogger._COLORS.get(color, '')}{text}{ProLogger._COLORS['reset']}"

    @staticmethod
    def info(component: str, message: str):
        """正常日志 - 白色"""
        tag = ProLogger._colorize(f"[pro:{component}]", "white")
        msg = ProLogger._colorize(message, "white")
        print(f"{tag} {msg}")

    @staticmethod
    def warn(component: str, message: str):
        """警告日志 - 黄色"""
        tag = ProLogger._colorize(f"[pro:{component}]", "yellow")
        icon = ProLogger._colorize("⚠", "yellow")
        msg = ProLogger._colorize(message, "yellow")
        print(f"{tag} {icon} {msg}")

    @staticmethod
    def error(component: str, message: str):
        """错误日志 - 红色"""
        tag = ProLogger._colorize(f"[pro:{component}]", "red")
        icon = ProLogger._colorize("✗", "red")
        msg = ProLogger._colorize(message, "red")
        print(f"{tag} {icon} {msg}")

    @staticmethod
    def debug(component: str, message: str):
        """调试日志 - 蓝色"""
        tag = ProLogger._colorize(f"[pro:{component}]", "blue")
        icon = ProLogger._colorize("ℹ", "blue")
        msg = ProLogger._colorize(message, "blue")
        print(f"{tag} {icon} {msg}")

    @staticmethod
    def tip(component: str, message: str):
        """提示日志 - 蓝色（用于小提示/额外信息）"""
        tag = ProLogger._colorize(f"[pro:{component}]", "blue")
        icon = ProLogger._colorize("→", "blue")
        msg = ProLogger._colorize(message, "blue")
        print(f"{tag} {icon} {msg}")
