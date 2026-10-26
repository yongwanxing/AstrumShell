"""控制台/编码相关的跨平台小工具

Windows 上有一个很容易踩的坑：**stdout 被重定向时**（管道、重定向到文件、CI 捕获），
Python 会用本地编码（中文系统上是 GBK）输出。这时打印 ``✓`` ``⚠`` ``✗`` 这类符号
会抛 ``UnicodeEncodeError``，直接把命令行脚本中断（服务端因为日志层做了降级才没事）。

命令行脚本应先调用 :func:`setup_console`，策略与 ``oss/cli.py`` 保持一致：

* 真实控制台（tty）：保留系统编码（中文正常显示），只把无法编码的字符降级为 ``?``；
* 被重定向/管道：统一改为 UTF-8 + 降级，日志文件和 CI 输出不会乱码。
"""

from __future__ import annotations

import sys
from typing import Iterable, Optional


def setup_console(streams: Optional[Iterable] = None) -> None:
    """让标准输出/错误输出不会因编码问题中断程序（幂等，可重复调用）"""
    for stream in (sys.stdout, sys.stderr) if streams is None else streams:
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:          # 被替换成非 TextIOWrapper 时直接跳过
            continue
        try:
            if getattr(stream, "isatty", lambda: False)():
                reconfigure(errors="replace")
            else:
                reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):    # 已关闭或不可重配置的流，忽略
            pass
