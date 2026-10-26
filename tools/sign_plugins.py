#!/usr/bin/env python3
"""
密钥生成与插件签名工具
- 生成 Upstream 官方密钥对
- 为所有官方插件签名
"""

import sys
import json
import base64
import time
import argparse
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend

# 允许 `python tools/sign_plugins.py` 直接运行（未安装 oss 时也能导入）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))      # 同目录工具模块

from oss.plugin.content_hash import plugin_tree_hash  # noqa: E402（必须在 sys.path 之后）
from oss.console import setup_console  # noqa: E402

# Windows 下输出被重定向时用本地编码会崩，先统一控制台策略
setup_console()

# ========== 配置 ==========
PROJECT_ROOT = Path(__file__).parent.parent  # 修复：tools 的上级目录
KEY_DIR = PROJECT_ROOT / "data" / "signature-verifier" / "keys"
STORE_DIR = PROJECT_ROOT / "store"

# 官方作者目录
OFFICIAL_AUTHORS = ["AstrumShell", "Upstream"]


def private_key_path(author: str) -> Path:
    """官方私钥路径"""
    return KEY_DIR / "private" / f"{author.lower()}_private.pem"


def load_or_create_keypair(author: str, new_keys: bool = False):
    """取得签名私钥：默认**复用**已存在的密钥，只有显式 --new-keys 才重新生成

    重新生成密钥会让所有已签名插件立即失效（信任锚也必须同步更新），
    所以默认绝不覆盖。轮换密钥请用：
        python tools/sign_plugins.py --new-keys
        python tools/update_trust_anchors.py
    """
    priv_path = private_key_path(author)
    if priv_path.exists() and not new_keys:
        print(f"  复用已存在私钥: {priv_path}")
        return serialization.load_pem_private_key(priv_path.read_bytes(), password=None)

    if priv_path.exists():
        print(f"  ⚠ 正在轮换密钥（旧密钥将被覆盖）: {priv_path}")
    private_key, _ = generate_keypair(author)
    return private_key


def public_pem_of(private_key) -> str:
    """导出公钥 PEM（用于写入信任锚）"""
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def generate_keypair(author: str):
    """生成 4096 位 RSA 密钥对"""
    print(f"\n{'='*60}")
    print(f"生成 {author} 的密钥对...")
    print(f"{'='*60}")
    
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    
    # 保存私钥
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    priv_dir = KEY_DIR / "private"
    priv_dir.mkdir(parents=True, exist_ok=True)
    priv_file = priv_dir / f"{author.lower()}_private.pem"
    priv_file.write_bytes(private_pem)
    print(f"私钥已保存: {priv_file}")
    
    # 保存公钥
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    pub_dir = KEY_DIR / "public"
    pub_dir.mkdir(parents=True, exist_ok=True)
    pub_file = pub_dir / f"{author}.pem"
    pub_file.write_bytes(public_pem)
    print(f"公钥已保存: {pub_file}")
    
    # 显示公钥（用于嵌入代码）
    print(f"\n--- 公钥 PEM (用于嵌入 main.py) ---")
    print(public_pem.decode())
    print(f"--- END ---\n")
    
    return private_key, public_key


def compute_plugin_hash(plugin_dir: Path) -> str:
    """计算插件目录的内容哈希

    统一委托给 oss.plugin.content_hash.plugin_tree_hash：文本文件按 LF 归一化、
    相对路径按 ``/`` 分隔，保证同一插件在 Windows / Linux / macOS 上哈希一致。
    """
    return plugin_tree_hash(plugin_dir)


def sign_plugin(plugin_dir: Path, private_key, signer_name: str, author: str):
    """为插件生成签名"""
    plugin_hash = compute_plugin_hash(plugin_dir)
    
    # 签名
    signed_data = f"{author}:{plugin_hash}".encode("utf-8")
    signature = private_key.sign(
        signed_data,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    # 写入签名文件
    sig_data = {
        "signature": base64.b64encode(signature).decode(),
        "signer": signer_name,
        "algorithm": "RSA-SHA256",
        "timestamp": time.time(),
        "plugin_hash": plugin_hash,
        "author": author
    }
    
    signature_file = plugin_dir / "SIGNATURE"
    # 固定 LF + UTF-8：Windows 下 write_text 默认写 CRLF 且用本地编码，
    # 会让同一个签名文件在不同平台字节不一致
    signature_file.write_text(json.dumps(sig_data, indent=2), encoding="utf-8", newline="\n")
    print(f"  ✓ 已签名: {plugin_dir.name} (哈希: {plugin_hash[:16]}...)")


def sign_namespace(author: str, private_key) -> int:
    """为某个命名空间（@{author}）下所有插件签名，返回签名数量"""
    author_dir = STORE_DIR / f"@{{{author}}}"
    if not author_dir.exists():
        print(f"警告: 命名空间目录不存在: {author_dir}")
        return 0

    count = 0
    for plugin_dir in sorted(author_dir.iterdir()):
        if not plugin_dir.is_dir():
            continue
        # 只要有 main.py 或 manifest.json 就是「插件」，都要签名
        if not ((plugin_dir / "main.py").exists() or (plugin_dir / "manifest.json").exists()):
            continue
        sign_plugin(plugin_dir, private_key, author, author)
        count += 1
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description="AstrumShell 插件签名工具")
    parser.add_argument("--new-keys", action="store_true",
                        help="重新生成密钥对（会作废所有现有签名，需再执行 tools/update_trust_anchors.py）")
    args = parser.parse_args(argv)

    print("="*60)
    print("AstrumShell 插件签名工具")
    print("="*60)

    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        print("错误: 未安装 cryptography 库")
        print("运行: pip install cryptography")
        return 1

    # 步骤 1: 准备各命名空间的密钥（默认复用，避免误轮换）
    print("\n步骤 1: 准备官方密钥对（默认复用已有私钥）...")
    keys = {}
    for author in OFFICIAL_AUTHORS:
        print(f"\n[{author}]")
        keys[author] = load_or_create_keypair(author, args.new_keys)

    # 步骤 2: 同步信任锚。
    # 信任锚常量就写在 signature-verifier 插件自己的 main.py 里，一旦同步，
    # 该插件内容哈希就变了 —— 所以必须「先同步信任锚、再签名」才能一次收敛。
    print("\n步骤 2: 同步信任锚（signature-verifier/main.py）...")
    try:
        from update_trust_anchors import sync_anchors
        anchors_ok, anchors_changed = sync_anchors(check=False)
        if anchors_changed:
            print("  → 信任锚已更新，随后的签名会覆盖 signature-verifier 的新内容")
        elif not anchors_ok:
            print("  ⚠ 信任锚与本地密钥不一致，且未能自动更新")
    except Exception as exc:
        print(f"  ⚠ 信任锚同步失败：{type(exc).__name__}: {exc}")

    # 步骤 3: 为各命名空间下的所有插件签名
    print("\n步骤 3: 为插件签名...")
    total = 0
    for author, private_key in keys.items():
        print(f"\n{'='*60}")
        print(f"为 @{{{author}}} 的插件签名...")
        print(f"{'='*60}")
        count = sign_namespace(author, private_key)
        total += count
        print(f"\n完成: 已签名 {count} 个 @{{{author}}} 插件")

    print("\n" + "="*60)
    print(f"全部完成，共签名 {total} 个插件")
    print("="*60)
    print(f"\n私钥位置: {KEY_DIR / 'private'}（已被 .gitignore 排除，请离线保管）")
    print("信任锚文件: store/@{AstrumShell}/signature-verifier/main.py")
    print("\n按下面的命令把新公钥写进信任锚（不要手工复制粘贴）：")
    print("    python tools/update_trust_anchors.py")
    print("验证签名：")
    print("    python tools/test_signature.py")
    print("    python tools/update_trust_anchors.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
