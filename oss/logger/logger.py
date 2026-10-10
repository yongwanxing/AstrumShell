"""日志系统 - 彩色日志"""
import sys


def _safe_print(text: str) -> None:
    """跨平台安全输出。

    日志里包含 emoji（⚠/✅/ℹ）时，在 Windows 的 GBK 控制台上直接 print 会抛
    UnicodeEncodeError 把整个服务打崩。这里捕获后按当前流编码降级输出，
    保证日志永不因编码问题中断程序。
    """
    try:
        print(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(enc, "replace").decode(enc, "replace"))


class Log:
    """通用彩色日志 - 所有插件可共用"""

    _TTY = sys.stdout.isatty()
    _C = {
        "reset": "\033[0m",
        "white": "\033[0;37m",
        "yellow": "\033[1;33m",
        "blue": "\033[1;34m",
        "red": "\033[1;31m",
        "green": "\033[0;32m",
    }

    @classmethod
    def _c(cls, text: str, color: str) -> str:
        if not cls._TTY:
            return text
        return f"{cls._C.get(color, '')}{text}{cls._C['reset']}"

    @classmethod
    def info(cls, tag: str, msg: str):
        _safe_print(f"{cls._c(f'[{tag}]', 'white')} {cls._c(msg, 'white')}")

    @classmethod
    def warn(cls, tag: str, msg: str):
        _safe_print(f"{cls._c(f'[{tag}]', 'yellow')} {cls._c('⚠', 'yellow')} {cls._c(msg, 'yellow')}")

    @classmethod
    def error(cls, tag: str, msg: str):
        _safe_print(f"{cls._c(f'[{tag}]', 'red')} {cls._c('✗', 'red')} {cls._c(msg, 'red')}")

    @classmethod
    def tip(cls, tag: str, msg: str):
        _safe_print(f"{cls._c(f'[{tag}]', 'blue')} {cls._c('ℹ', 'blue')} {cls._c(msg, 'blue')}")

    @classmethod
    def ok(cls, tag: str, msg: str):
        _safe_print(f"{cls._c(f'[{tag}]', 'white')} {cls._c(msg, 'white')}")


class Logger:
    """日志记录器（兼容旧接口）"""

    def info(self, msg: str, **kwargs):
        tag = kwargs.get("tag", "INFO")
        Log.info(tag, msg)

    def warn(self, msg: str, **kwargs):
        tag = kwargs.get("tag", "WARN")
        Log.warn(tag, msg)

    def error(self, msg: str, **kwargs):
        tag = kwargs.get("tag", "ERROR")
        Log.error(tag, msg)

    def debug(self, msg: str, **kwargs):
        tag = kwargs.get("tag", "DEBUG")
        Log.tip(tag, msg)
