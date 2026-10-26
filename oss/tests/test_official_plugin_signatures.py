"""官方插件签名链回归测试

只依赖 signature-verifier 里**内嵌的信任锚公钥**（不需要私钥），所以能在 CI 上跑：
一旦有人改了插件文件却忘了 `python tools/sign_plugins.py`，这里会立刻失败。

覆盖两类目录：
* ``store/@{AstrumShell}``：本项目官方插件
* ``store/@{Upstream}``：上游社区插件
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORE_DIR = PROJECT_ROOT / "store"
VERIFIER_DIR = STORE_DIR / "@{AstrumShell}" / "signature-verifier"
OFFICIAL_NAMESPACES = ("AstrumShell", "Upstream")

pytest.importorskip("cryptography")


def _load_verifier_module():
    """按文件路径加载签名插件，避免与仓库根目录的 main.py 重名冲突"""
    spec = importlib.util.spec_from_file_location(
        "astrum_signature_verifier_ci", VERIFIER_DIR / "main.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _official_plugin_dirs():
    """列出所有可加载的官方插件目录（带 main.py 才算插件）"""
    found = []
    for namespace in OFFICIAL_NAMESPACES:
        namespace_dir = STORE_DIR / f"@{{{namespace}}}"
        if not namespace_dir.is_dir():
            continue
        for plugin_dir in sorted(namespace_dir.iterdir()):
            if plugin_dir.is_dir() and (plugin_dir / "main.py").exists():
                found.append((namespace, plugin_dir))
    return found


PLUGIN_DIRS = _official_plugin_dirs()


def test_official_plugin_dirs_found():
    """防止插件目录被整体改名/搬走后测试静默通过"""
    assert len(PLUGIN_DIRS) >= 20, f"官方插件数量异常（找到 {len(PLUGIN_DIRS)} 个）"


@pytest.mark.parametrize(
    "namespace,plugin_dir",
    PLUGIN_DIRS,
    ids=[f"{ns}-{p.name}" for ns, p in PLUGIN_DIRS],
)
def test_official_plugin_signature_is_valid(namespace, plugin_dir, tmp_path):
    """每个官方插件的 SIGNATURE 都必须能用内嵌信任锚验签通过"""
    verifier_module = _load_verifier_module()
    verifier = verifier_module.SignatureVerifier(key_dir=str(tmp_path / "keys"))

    ok, message = verifier.verify_plugin(plugin_dir, namespace)
    assert ok, (
        f"{namespace}/{plugin_dir.name} 验签失败：{message}\n"
        f"提示：改动插件后需要重新签名 → python tools/sign_plugins.py"
    )
