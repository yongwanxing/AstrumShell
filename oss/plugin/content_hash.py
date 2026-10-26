"""插件内容哈希（跨平台一致）

插件目录哈希用于插件的签名与验签。如果直接哈希原始字节，同一份插件代码在
Windows 与 Linux / macOS 上会算出不同的哈希，导致跨平台验签失败，原因有三：

1. 换行不同：Windows 检出/编辑后可能是 ``CRLF``，而仓库里是 ``LF``；
2. 路径分隔符不同：``str(相对路径)`` 在 Windows 上是 ``a\\b``，POSIX 上是 ``a/b``；
3. 缓存文件：``__pycache__/*.pyc`` 与 Python 版本、平台绑定，本不该参与哈希。

因此本模块提供唯一实现，**签名端与验签端都必须调用它**，规则如下：

* 目录内相对路径统一用 ``/`` 分隔，并按该相对路径排序后依次哈希；
* 文本文件在哈希前把 ``CRLF`` / ``CR`` 归一为 ``LF``，二进制文件保持原样；
* 默认跳过 ``SIGNATURE``、``__pycache__``（及 ``.git`` 等目录）与 ``*.pyc`` / ``*.pyo``。

只要插件内容相同，无论在哪个平台打包或解包，得到的哈希都一致。
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import FrozenSet, List, Tuple, Union

PathLike = Union[str, Path]

#: 明确按文本处理的扩展名（不在其中的文件，能按 UTF-8 解码时也按文本处理）
TEXT_SUFFIXES: FrozenSet[str] = frozenset({
    ".py", ".pyi", ".pyw", ".json", ".jsonc", ".json5", ".md", ".markdown", ".rst",
    ".txt", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".conf", ".properties",
    ".html", ".htm", ".css", ".scss", ".less", ".js", ".mjs", ".cjs", ".jsx",
    ".ts", ".tsx", ".vue", ".svelte", ".sql", ".xml", ".svg", ".env",
    ".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1",
})

#: 默认不参与哈希的文件名（签名文件自身不能参与哈希）
SKIP_NAMES: FrozenSet[str] = frozenset({"SIGNATURE"})

#: 默认不参与哈希的目录名（缓存 / 依赖 / 编辑器目录）
SKIP_DIR_NAMES: FrozenSet[str] = frozenset({
    "__pycache__", ".git", ".hg", ".svn", ".idea", ".vscode", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "node_modules", ".venv", "venv",
})

#: 默认不参与哈希的后缀（编译产物）
SKIP_SUFFIXES: FrozenSet[str] = frozenset({".pyc", ".pyo", ".pyd"})


def _is_text(path: Path, data: bytes) -> bool:
    """判断文件内容是否按文本处理（文本才做换行归一化）"""
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    if b"\x00" in data[:8192]:          # 含 NUL 字节 → 二进制
        return False
    try:
        data.decode("utf-8")            # 能当 UTF-8 解码 → 视为文本
    except UnicodeDecodeError:
        return False
    return True


def normalized_content(file_path: PathLike) -> bytes:
    """返回用于哈希的文件内容：文本文件统一为 LF 换行，二进制文件原样返回"""
    path = Path(file_path)
    data = path.read_bytes()
    if not _is_text(path, data):
        return data
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def iter_plugin_files(
    plugin_dir: PathLike,
    skip_names: FrozenSet[str] = SKIP_NAMES,
    skip_dir_names: FrozenSet[str] = SKIP_DIR_NAMES,
    skip_suffixes: FrozenSet[str] = SKIP_SUFFIXES,
) -> List[Tuple[str, Path]]:
    """列出参与哈希的文件，返回 (POSIX 风格相对路径, 绝对路径) 并按相对路径排序"""
    root = Path(plugin_dir)
    entries: List[Tuple[str, Path]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in skip_dir_names for part in rel_parts[:-1]):
            continue
        if path.name in skip_names or path.suffix.lower() in skip_suffixes:
            continue
        entries.append(("/".join(rel_parts), path))
    entries.sort(key=lambda item: item[0])
    return entries


def plugin_tree_hash(
    plugin_dir: PathLike,
    skip_names: FrozenSet[str] = SKIP_NAMES,
    skip_dir_names: FrozenSet[str] = SKIP_DIR_NAMES,
    skip_suffixes: FrozenSet[str] = SKIP_SUFFIXES,
) -> str:
    """计算插件目录的内容哈希（同一内容在任何平台结果一致）"""
    hasher = hashlib.sha256()
    for rel_path, file_path in iter_plugin_files(plugin_dir, skip_names, skip_dir_names, skip_suffixes):
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(normalized_content(file_path))
    return hasher.hexdigest()
