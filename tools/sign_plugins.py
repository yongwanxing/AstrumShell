#!/usr/bin/env python3
"""
密钥生成与插件签名工具
- 生成 Upstream 官方密钥对
- 为所有官方插件签名
"""

import sys
import json
import base64
import hashlib
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend

# ========== 配置 ==========
PROJECT_ROOT = Path(__file__).parent.parent  # 修复：tools 的上级目录
KEY_DIR = PROJECT_ROOT / "data" / "signature-verifier" / "keys"
STORE_DIR = PROJECT_ROOT / "store"

# 官方作者目录
OFFICIAL_AUTHORS = ["AstrumShell", "Upstream"]


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
    signature_file.write_text(json.dumps(sig_data, indent=2))
    print(f"  ✓ 已签名: {plugin_dir.name} (哈希: {plugin_hash[:16]}...)")


def sign_all_plugins(private_key):
    """为所有官方插件签名"""
    for author in OFFICIAL_AUTHORS:
        author_dir = STORE_DIR / f"@{{{author}}}"
        if not author_dir.exists():
            print(f"\n警告: 作者目录不存在: {author_dir}")
            continue
        
        print(f"\n{'='*60}")
        print(f"为 @{{{author}}} 的插件签名...")
        print(f"{'='*60}")
        
        count = 0
        for plugin_dir in sorted(author_dir.iterdir()):
            if plugin_dir.is_dir() and (plugin_dir / "manifest.json").exists():
                sign_plugin(plugin_dir, private_key, author, author)
                count += 1
        
        print(f"\n完成: 已签名 {count} 个 @{author} 插件")


def main():
    print("="*60)
    print("AstrumShell 插件签名工具")
    print("="*60)

    # 检查 cryptography
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        print("错误: 未安装 cryptography 库")
        print("运行: pip install cryptography")
        sys.exit(1)

    # 步骤 1: 生成密钥对
    print("\n步骤 1: 生成 Upstream 官方密钥对...")
    upstream_priv, upstream_pub = generate_keypair("Upstream")

    print("\n步骤 1b: 生成 AstrumShell 官方密钥对...")
    foss_priv, foss_pub = generate_keypair("AstrumShell")

    # 步骤 2: 为所有官方插件签名（使用对应的密钥）
    print("\n步骤 2: 为所有官方插件签名...")
    
    # Upstream 的插件用 Upstream 密钥签名
    upstream_dir = STORE_DIR / "@{Upstream}"
    if upstream_dir.exists():
        print(f"\n{'='*60}")
        print("为 @{Upstream} 的插件使用 Upstream 密钥签名...")
        print(f"{'='*60}")
        for plugin_dir in sorted(upstream_dir.iterdir()):
            if plugin_dir.is_dir() and (plugin_dir / "manifest.json").exists():
                sign_plugin(plugin_dir, upstream_priv, "Upstream", "Upstream")
    
    # AstrumShell 的插件用 AstrumShell 密钥签名
    foss_dir = STORE_DIR / "@{AstrumShell}"
    if foss_dir.exists():
        print(f"\n{'='*60}")
        print("为 @{AstrumShell} 的插件使用 AstrumShell 密钥签名...")
        print(f"{'='*60}")
        for plugin_dir in sorted(foss_dir.iterdir()):
            if plugin_dir.is_dir() and (plugin_dir / "manifest.json").exists():
                sign_plugin(plugin_dir, foss_priv, "AstrumShell", "AstrumShell")
    
    print("\n" + "="*60)
    print("全部完成!")
    print("="*60)
    print(f"\n密钥位置: {KEY_DIR}")
    print("请将公钥嵌入 signature-verifier/main.py 的 UPSTREAM_PUBLIC_KEY_PEM 变量")
    print("并妥善保管私钥，不要提交到版本控制系统!")


if __name__ == "__main__":
    main()
