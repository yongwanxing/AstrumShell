#!/usr/bin/env python3
"""AstrumShell 主入口 - 兼容旧版启动方式

此文件用于兼容 README 中描述的 `python main.py` 启动方式。
推荐使用 `astrum serve` 命令启动。
"""
import sys
from pathlib import Path

# 确保 workspace 在 Python 路径中
workspace_dir = Path(__file__).parent.resolve()
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from oss.cli import main

if __name__ == "__main__":
    main()
