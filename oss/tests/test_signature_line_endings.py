"""插件签名跨平台一致性回归测试

背景：插件目录哈希原先直接哈希原始字节，并且用 ``str(相对路径)`` 参与哈希，
导致同一份插件代码在不同平台算出不同哈希，跨平台验签失败：

* Windows 检出/编辑后可能是 CRLF，POSIX 是 LF；
* ``str(相对路径)`` 在 Windows 是 ``a\\b``，POSIX 是 ``a/b``；
* ``__pycache__/*.pyc`` 会随解释器版本变化而污染哈希。

修复后统一走 :mod:`oss.plugin.content_hash`（文本按 LF 归一化 + 相对路径按
``/`` 分隔 + 跳过缓存），本测试锁定该行为。CI 会在
ubuntu / windows / macos × Python 3.10 / 3.12 / 3.13 上执行它。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERIFIER_DIR = PROJECT_ROOT / "store" / "@{AstrumShell}" / "signature-verifier"

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402

from oss.plugin.content_hash import iter_plugin_files, plugin_tree_hash  # noqa: E402

AUTHOR = "crossplatformtest"
TEXT_FILES = ("manifest.json", "main.py", "sub/helper.py")


def _load_verifier_module():
    """按文件路径加载签名插件，避免与仓库根目录的 main.py 重名冲突"""
    spec = importlib.util.spec_from_file_location(
        "astrum_signature_verifier_main", VERIFIER_DIR / "main.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def verifier_module():
    return _load_verifier_module()


@pytest.fixture(scope="module")
def key_dir(tmp_path_factory):
    """生成一次性测试密钥，公钥放到 <key_dir>/public/<author>.pem 供验签使用"""
    root = tmp_path_factory.mktemp("keys")
    (root / "private").mkdir()
    (root / "public").mkdir()

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (root / "private" / f"{AUTHOR}_private.pem").write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    (root / "public" / f"{AUTHOR}.pem").write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return root


def _make_plugin(root: Path) -> Path:
    """构造测试插件：顶层文本、子目录文本、二进制、缓存文件"""
    plugin = root / "sample-plugin"
    (plugin / "sub").mkdir(parents=True)
    (plugin / "assets").mkdir()
    (plugin / "__pycache__").mkdir()

    (plugin / "manifest.json").write_text('{"name": "sample-plugin"}', encoding="utf-8", newline="\n")
    (plugin / "main.py").write_text("def New():\n    return None\n", encoding="utf-8", newline="\n")
    (plugin / "sub" / "helper.py").write_text("VALUE = 1\n", encoding="utf-8", newline="\n")
    (plugin / "assets" / "logo.bin").write_bytes(b"\x00\x01\r\n\x02")  # 二进制，不应被归一化
    (plugin / "__pycache__" / "main.cpython-311.pyc").write_bytes(b"cache")
    return plugin


def _to_crlf(plugin_dir: Path) -> None:
    """把所有文本文件转成 CRLF，模拟 Windows 检出/编辑后的工作区"""
    for name in TEXT_FILES:
        path = plugin_dir / name
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))


def _sign(verifier_module, key_dir: Path, plugin: Path) -> None:
    signer = verifier_module.SignatureSigner(str(key_dir / "private" / f"{AUTHOR}_private.pem"))
    signer.sign_plugin(plugin, AUTHOR, AUTHOR)


def test_sign_and_verify_on_current_platform(verifier_module, key_dir, tmp_path):
    """当前平台：签名后可以正常验签"""
    plugin = _make_plugin(tmp_path)
    _sign(verifier_module, key_dir, plugin)

    verifier = verifier_module.SignatureVerifier(key_dir=str(key_dir))
    ok, msg = verifier.verify_plugin(plugin, AUTHOR)
    assert ok, f"签名验证应当通过，实际: {msg}"


def test_signature_verifies_after_crlf_conversion(verifier_module, key_dir, tmp_path):
    """跨平台核心：签名后再把文本文件改成 CRLF，验签仍应通过"""
    plugin = _make_plugin(tmp_path)
    _sign(verifier_module, key_dir, plugin)

    _to_crlf(plugin)
    assert b"\r\n" in (plugin / "main.py").read_bytes(), "前置条件：文件应已变为 CRLF"

    verifier = verifier_module.SignatureVerifier(key_dir=str(key_dir))
    ok, msg = verifier.verify_plugin(plugin, AUTHOR)
    assert ok, f"CRLF 与 LF 应视为同一内容，验签不应失败: {msg}"


def test_signature_verifies_when_signed_from_crlf(verifier_module, key_dir, tmp_path):
    """反向场景：在 CRLF 工作区签名，换成 LF 后验签仍应通过"""
    plugin = _make_plugin(tmp_path)
    _to_crlf(plugin)
    _sign(verifier_module, key_dir, plugin)

    for name in TEXT_FILES:                       # 转回 LF
        path = plugin / name
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))

    verifier = verifier_module.SignatureVerifier(key_dir=str(key_dir))
    ok, msg = verifier.verify_plugin(plugin, AUTHOR)
    assert ok, f"LF 与 CRLF 应视为同一内容，验签不应失败: {msg}"


def test_tampering_is_still_detected(verifier_module, key_dir, tmp_path):
    """归一化不能削弱完整性：改一个字节必须验签失败"""
    plugin = _make_plugin(tmp_path)
    _sign(verifier_module, key_dir, plugin)

    (plugin / "sub" / "helper.py").write_text("VALUE = 2\n", encoding="utf-8", newline="\n")

    verifier = verifier_module.SignatureVerifier(key_dir=str(key_dir))
    ok, msg = verifier.verify_plugin(plugin, AUTHOR)
    assert not ok, "内容被篡改后验签必须失败"


def test_tree_hash_ignores_line_endings_and_cache(tmp_path):
    """哈希本身：换行、缓存文件、SIGNATURE 都不应影响结果"""
    plugin = _make_plugin(tmp_path)
    baseline = plugin_tree_hash(plugin)

    _to_crlf(plugin)
    assert plugin_tree_hash(plugin) == baseline, "换行差异不应改变哈希"

    (plugin / "__pycache__" / "extra.cpython-312.pyc").write_bytes(b"more cache")
    assert plugin_tree_hash(plugin) == baseline, "缓存文件不应参与哈希"

    (plugin / "SIGNATURE").write_text("{}", encoding="utf-8", newline="\n")
    assert plugin_tree_hash(plugin) == baseline, "SIGNATURE 自身不应参与哈希"


def test_tree_hash_uses_posix_separators(tmp_path):
    """子目录插件的哈希不应受平台路径分隔符影响"""
    plugin = _make_plugin(tmp_path)
    rel_paths = [rel for rel, _ in iter_plugin_files(plugin)]

    assert "sub/helper.py" in rel_paths, f"相对路径应统一用 / 分隔，实际: {rel_paths}"
    assert not any("\\" in rel for rel in rel_paths), f"不应出现反斜杠: {rel_paths}"

