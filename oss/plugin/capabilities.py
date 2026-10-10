"""能力扫描器 - 自动扫描插件支持的能力"""
import ast
from pathlib import Path
from typing import Any


def scan_capabilities(plugin_dir: Path) -> Any:
    """扫描插件目录，自动发现支持的能力"""
    capabilities: set[str] = set()
    main_file = plugin_dir / "main.py"

    if not main_file.exists():
        return capabilities

    with open(main_file, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    # 扫描规则：
    # 1. 检查是否导出了特定的类或函数
    # 2. 检查是否有特定的装饰器或标记
    # 3. 检查 import 语句（表示依赖了某个能力）

    for node in ast.walk(tree):
        # 检查类定义
        if isinstance(node, ast.ClassDef):
            class_name = node.name
            # 如果类名包含特定后缀，认为是能力提供者
            if class_name.endswith("Provider"):
                cap_name = class_name.replace("Provider", "").lower()
                capabilities.add(cap_name)
            elif class_name.endswith("Mixin"):
                cap_name = class_name.replace("Mixin", "").lower()
                capabilities.add(cap_name)
            elif class_name.endswith("Support"):
                cap_name = class_name.replace("Support", "").lower()
                capabilities.add(cap_name)

        # 检查函数定义
        elif isinstance(node, ast.FunctionDef):
            func_name = node.name
            # 检查是否有能力相关的装饰器
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name):
                    if decorator.id.startswith("provides_"):
                        cap_name = decorator.id.replace("provides_", "")
                        capabilities.add(cap_name)
                elif isinstance(decorator, ast.Attribute):
                    if decorator.attr.startswith("provides_"):
                        cap_name = decorator.attr.replace("provides_", "")
                        capabilities.add(cap_name)

        # 检查 import 语句（表示使用了某个能力）
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "circuit" in alias.name.lower() or "breaker" in alias.name.lower():
                    capabilities.add("circuit_breaker")
                elif "retry" in alias.name.lower():
                    capabilities.add("retry")
                elif "cache" in alias.name.lower():
                    capabilities.add("cache")

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                if "circuit" in node.module.lower() or "breaker" in node.module.lower():
                    capabilities.add("circuit_breaker")
                elif "retry" in node.module.lower():
                    capabilities.add("retry")
                elif "cache" in node.module.lower():
                    capabilities.add("cache")

    return capabilities
