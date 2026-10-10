#!/usr/bin/env python3
"""
签名验证测试脚本
测试签名验证功能是否正常工作
"""

import sys
import json
import base64
import hashlib
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "store/@{AstrumShell}/signature-verifier"))

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

# 导入签名验证插件
from main import SignatureVerifier, SignatureSigner


def test_verify_official_plugins():
    """测试验证所有已签名的官方插件"""
    print("="*60)
    print("测试 1: 验证所有官方插件签名")
    print("="*60)
    
    store_dir = Path(__file__).parent.parent / "store"
    verifier = SignatureVerifier(key_dir="./data/signature-verifier/keys")
    
    authors = ["AstrumShell", "Upstream"]
    total = 0
    passed = 0
    failed = 0
    
    for author in authors:
        author_dir = store_dir / f"@{{{author}}}"
        if not author_dir.exists():
            continue
        
        print(f"\n--- @{author} ---")
        for plugin_dir in sorted(author_dir.iterdir()):
            if plugin_dir.is_dir() and (plugin_dir / "manifest.json").exists():
                total += 1
                valid, msg = verifier.verify_plugin(plugin_dir, author)
                status = "✅ 通过" if valid else "❌ 失败"
                print(f"  {status}: {plugin_dir.name} - {msg}")
                if valid:
                    passed += 1
                else:
                    failed += 1
    
    print(f"\n{'='*60}")
    print(f"结果: {passed}/{total} 通过, {failed} 失败")
    print(f"{'='*60}")
    return failed == 0


def test_tamper_detection():
    """测试篡改检测"""
    print("\n" + "="*60)
    print("测试 2: 篡改检测")
    print("="*60)
    
    store_dir = Path(__file__).parent.parent / "store"
    verifier = SignatureVerifier(key_dir="./data/signature-verifier/keys")
    
    # 选择一个测试插件
    test_plugin = store_dir / "@{AstrumShell}" / "dashboard"
    if not test_plugin.exists():
        print("跳过: dashboard 插件不存在")
        return True
    
    # 验证原始签名
    valid_before, msg_before = verifier.verify_plugin(test_plugin, "AstrumShell")
    print(f"\n篡改前: {'✅ 有效' if valid_before else '❌ 无效'} - {msg_before}")
    
    if not valid_before:
        print("警告: 原始签名已无效，跳过篡改测试")
        return False
    
    # 创建一个临时篡改文件
    tamper_file = test_plugin / "__tamper_test__.tmp"
    tamper_file.write_text("tampered content")
    
    # 验证篡改后的签名
    valid_after, msg_after = verifier.verify_plugin(test_plugin, "AstrumShell")
    print(f"篡改后: {'✅ 有效' if valid_after else '❌ 无效'} - {msg_after}")
    
    # 清理
    tamper_file.unlink()
    
    # 再次验证应该恢复有效
    valid_clean, msg_clean = verifier.verify_plugin(test_plugin, "AstrumShell")
    print(f"清理后: {'✅ 有效' if valid_clean else '❌ 无效'} - {msg_clean}")
    
    # 预期：篡改后无效，清理后有效
    success = not valid_after and valid_clean
    print(f"\n{'='*60}")
    print(f"篡改检测: {'✅ 成功' if success else '❌ 失败'}")
    print(f"{'='*60}")
    return success


def test_missing_signature():
    """测试缺失签名文件"""
    print("\n" + "="*60)
    print("测试 3: 缺失签名检测")
    print("="*60)
    
    store_dir = Path(__file__).parent.parent / "store"
    verifier = SignatureVerifier(key_dir="./data/signature-verifier/keys")
    
    # 选择一个插件并临时移除签名
    test_plugin = store_dir / "@{AstrumShell}" / "json-codec"
    if not test_plugin.exists():
        print("跳过: json-codec 插件不存在")
        return True
    
    sig_file = test_plugin / "SIGNATURE"
    if not sig_file.exists():
        print("跳过: json-codec 没有签名文件")
        return True
    
    # 备份签名
    backup = sig_file.read_text()
    sig_file.unlink()
    
    # 验证
    valid, msg = verifier.verify_plugin(test_plugin, "AstrumShell")
    print(f"无签名: {'✅ 有效' if valid else '❌ 无效'} - {msg}")
    
    # 恢复
    sig_file.write_text(backup)
    
    valid_restored, msg_restored = verifier.verify_plugin(test_plugin, "AstrumShell")
    print(f"恢复后: {'✅ 有效' if valid_restored else '❌ 无效'} - {msg_restored}")
    
    success = not valid and valid_restored
    print(f"\n{'='*60}")
    print(f"缺失签名检测: {'✅ 成功' if success else '❌ 失败'}")
    print(f"{'='*60}")
    return success


def test_official_check():
    """测试 is_official_plugin 方法"""
    print("\n" + "="*60)
    print("测试 4: 官方插件识别")
    print("="*60)
    
    store_dir = Path(__file__).parent.parent / "store"
    verifier = SignatureVerifier(key_dir="./data/signature-verifier/keys")
    
    # 测试官方插件
    official_plugin = store_dir / "@{AstrumShell}" / "dashboard"
    is_official = verifier.is_official_plugin(official_plugin)
    print(f"dashboard 是官方插件: {'✅ 是' if is_official else '❌ 否'}")
    
    success = is_official
    print(f"\n{'='*60}")
    print(f"官方插件识别: {'✅ 成功' if success else '❌ 失败'}")
    print(f"{'='*60}")
    return success


def main():
    print("AstrumShell 签名验证系统测试")
    print("="*60)
    
    results = []
    
    results.append(("官方插件验证", test_verify_official_plugins()))
    results.append(("篡改检测", test_tamper_detection()))
    results.append(("缺失签名检测", test_missing_signature()))
    results.append(("官方插件识别", test_official_check()))
    
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {status}: {name}")
    
    all_passed = all(r[1] for r in results)
    print(f"\n{'='*60}")
    print(f"总体结果: {'✅ 全部通过' if all_passed else '❌ 有失败'}")
    print(f"{'='*60}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
