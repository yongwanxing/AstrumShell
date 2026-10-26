#!/usr/bin/env python3
"""
把本地官方密钥的公钥写入 signature-verifier 的信任锚常量

用法：
    python tools/update_trust_anchors.py          # 写入（--new-keys 轮换后必须执行）
    python tools/update_trust_anchors.py --check   # 只检查是否一致，不修改文件

为什么需要这个脚本：信任锚是嵌在 `signature-verifier/main.py` 里的 PEM 常量，
手工复制很容易抄错或忘记同步，结果就是「签名明明有效却验签失败」。
"""

import argparse
import ast
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 允许 `python tools/update_trust_anchors.py` 直接运行（未安装 oss 时也能导入）
sys.path.insert(0, str(PROJECT_ROOT))

from oss.console import setup_console  # noqa: E402

setup_console()

KEY_DIR = PROJECT_ROOT / "data" / "signature-verifier" / "keys"
ANCHOR_FILE = PROJECT_ROOT / "store" / "@{AstrumShell}" / "signature-verifier" / "main.py"

#: 信任锚变量名 -> 对应的密钥名（密钥文件为 <小写名>_private.pem / <名>.pem）
ANCHORS = {
    "UPSTREAM_PUBLIC_KEY_PEM": "Upstream",
    "ASTRUMSHELL_PUBLIC_KEY_PEM": "AstrumShell",
}


def load_public_pem(author: str) -> str:
    """取得公钥 PEM：优先由私钥推导（保证与签名私钥严格对应），否则读 public/<作者>.pem"""
    from cryptography.hazmat.primitives import serialization

    private_path = KEY_DIR / "private" / f"{author.lower()}_private.pem"
    public_path = KEY_DIR / "public" / f"{author}.pem"

    if private_path.exists():
        key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
        public_key = key.public_key()
    elif public_path.exists():
        public_key = serialization.load_pem_public_key(public_path.read_bytes())
    else:
        raise FileNotFoundError(
            f"找不到 {author} 的密钥（{private_path} 或 {public_path}）；"
            f"请先执行 python tools/sign_plugins.py"
        )

    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode().strip()


def sync_anchors(check: bool = False) -> tuple[bool, bool]:
    """把本地密钥的公钥同步进信任锚常量

    返回 ``(是否全部一致, 是否修改了文件)``。``check=True`` 时只检查不写文件。

    注意：信任锚就写在 signature-verifier 插件自己的 main.py 里，所以同步完成后
    **该插件的内容哈希会变、它的 SIGNATURE 必须重新生成**。调用方（推荐
    ``tools/sign_plugins.py``）会在同步之后再签名，从而一次收敛。
    """
    try:
        from cryptography.hazmat.primitives import serialization  # noqa: F401
    except ImportError:
        print("错误: 未安装 cryptography 库（pip install cryptography）")
        return False, False

    if not ANCHOR_FILE.exists():
        print(f"错误: 信任锚文件不存在: {ANCHOR_FILE}")
        return False, False

    text = ANCHOR_FILE.read_text(encoding="utf-8")
    new_text = text
    ok_all = True

    for var, author in ANCHORS.items():
        pattern = re.compile(r'(' + var + r'\s*=\s*""")(.*?)(""")', re.S)
        matched = pattern.search(new_text)
        if not matched:
            print(f"  ✗ {var}: 未找到该常量")
            ok_all = False
            continue

        try:
            pem = load_public_pem(author)
        except FileNotFoundError as exc:
            print(f"  ✗ {var}: {exc}")
            ok_all = False
            continue

        current = matched.group(2).strip()
        if current == pem:
            print(f"  ✓ {var} 与 {author} 密钥一致（{pem.splitlines()[1][:16]}…）")
            continue

        ok_all = False
        if check:
            print(f"  ✗ {var} 与 {author} 密钥不一致（库里是 {current.splitlines()[1][:16]}…，"
                  f"本地是 {pem.splitlines()[1][:16]}…）")
        else:
            new_text = pattern.sub(lambda m: m.group(1) + pem + m.group(3), new_text, count=1)
            print(f"  → 已更新 {var}（{author}）")

    changed = new_text != text
    if changed:
        ast.parse(new_text)                  # 写之前先做语法检查，避免写坏源文件
        ANCHOR_FILE.write_text(new_text, encoding="utf-8", newline="\n")
        print(f"\n已写入: {ANCHOR_FILE}")
        print("⚠ signature-verifier 插件自身内容已变化，需要重新签名（tools/sign_plugins.py 会自动处理）")
    return ok_all, changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="同步 signature-verifier 的信任锚公钥")
    parser.add_argument("--check", action="store_true",
                        help="只检查信任锚是否与本地密钥一致，返回码 0/1")
    args = parser.parse_args(argv)

    ok_all, changed = sync_anchors(check=args.check)

    if args.check:
        print("\n信任锚状态: " + ("一致 ✓" if ok_all else "不一致 ✗"))
        return 0 if ok_all else 1

    if not changed:
        print("\n信任锚无需修改 ✓")
    else:
        print("\n下一步：python tools/sign_plugins.py（重新签名）")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
