#!/usr/bin/env python3
"""
为 dependency 和 signature-verifier 插件签名
"""

import sys
import json
import base64
import hashlib
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

# ========== 配置 ==========
PROJECT_ROOT = Path(__file__).parent.parent
PRIVATE_KEY_FILE = PROJECT_ROOT / "data" / "signature-verifier" / "keys" / "private" / "astrumshell_private.pem"

PLUGINS = ["dependency", "signature-verifier"]


def compute_plugin_hash(plugin_dir: Path) -> str:
    """计算插件目录的内容哈希"""
    hasher = hashlib.sha256()
    files_to_hash = []
    for file_path in sorted(plugin_dir.rglob("*")):
        if file_path.is_file() and file_path.name != "SIGNATURE":
            rel_path = file_path.relative_to(plugin_dir)
            files_to_hash.append((str(rel_path), file_path))

    for rel_path, file_path in files_to_hash:
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(file_path.read_bytes())

    return hasher.hexdigest()


def sign_plugin(plugin_dir: Path):
    """为插件签名"""
    # 加载私钥
    print(f"加载私钥: {PRIVATE_KEY_FILE}")
    private_key = serialization.load_pem_private_key(
        PRIVATE_KEY_FILE.read_bytes(),
        password=None,
        backend=default_backend()
    )

    # 计算插件哈希
    print(f"计算插件目录哈希: {plugin_dir.name}...")
    plugin_hash = compute_plugin_hash(plugin_dir)
    print(f"哈希: {plugin_hash}")

    # 签名
    signed_data = f"AstrumShell:{plugin_hash}".encode("utf-8")
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
        "signer": "AstrumShell",
        "algorithm": "RSA-SHA256",
        "timestamp": time.time(),
        "plugin_hash": plugin_hash,
        "author": "AstrumShell"
    }

    signature_file = plugin_dir / "SIGNATURE"
    signature_file.write_text(json.dumps(sig_data, indent=2))
    print(f"✓ 已签名: {plugin_dir.name}")


def main():
    if not PRIVATE_KEY_FILE.exists():
        print(f"错误: 私钥文件不存在: {PRIVATE_KEY_FILE}")
        sys.exit(1)

    store_dir = PROJECT_ROOT / "store" / "@{AstrumShell}"
    
    for plugin_name in PLUGINS:
        plugin_dir = store_dir / plugin_name
        if plugin_dir.exists():
            sign_plugin(plugin_dir)
        else:
            print(f"警告: 插件目录不存在: {plugin_dir}")

    print("\n完成!")


if __name__ == "__main__":
    main()
