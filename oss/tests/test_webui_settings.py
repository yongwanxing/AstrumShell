"""WebUI 设置存储与设置页渲染的单元测试

设置是「持久化 + 校验」的关键路径：非法值必须被拒绝、损坏的数据必须能回落默认，
否则一个坏配置就会让控制台起不来。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEBUI_DIR = PROJECT_ROOT / "store" / "@{AstrumShell}" / "webui"
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULTS = {
    "theme": "dark",
    "language": "zh-CN",
    "dashboard_auto_refresh": True,
    "dashboard_refresh_interval": 2,
}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


settings_mod = _load("webui_settings", WEBUI_DIR / "core" / "settings.py")
page_mod = _load("webui_settings_page", WEBUI_DIR / "core" / "settings_page.py")


class FakeStorage:
    """模拟 plugin-storage 的键值接口"""

    def __init__(self, data=None):
        self.data = dict(data or {})

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value


@pytest.fixture()
def store(tmp_path):
    return settings_mod.SettingsStore(storage=FakeStorage())


def test_defaults_when_empty(store):
    assert store.load() == DEFAULTS


def test_save_and_reload(store):
    saved = store.save({"theme": "light", "dashboard_refresh_interval": 5})
    assert saved["theme"] == "light"
    assert saved["dashboard_refresh_interval"] == 5

    # 用同一后端重新构造一次 = 模拟重启后读取
    reloaded = settings_mod.SettingsStore(storage=store.storage).load()
    assert reloaded == saved


def test_reject_unknown_key(store):
    with pytest.raises(ValueError):
        store.save({"hack": 1})


def test_reject_invalid_theme(store):
    with pytest.raises(ValueError):
        store.save({"theme": "neon"})


def test_interval_bounds(store):
    with pytest.raises(ValueError):
        store.save({"dashboard_refresh_interval": 0})
    with pytest.raises(ValueError):
        store.save({"dashboard_refresh_interval": 61})
    assert store.save({"dashboard_refresh_interval": 60})["dashboard_refresh_interval"] == 60


def test_type_coercion(store):
    saved = store.save({"dashboard_auto_refresh": "false", "dashboard_refresh_interval": "7"})
    assert saved["dashboard_auto_refresh"] is False
    assert saved["dashboard_refresh_interval"] == 7


def test_reset(store):
    store.save({"theme": "light"})
    assert store.reset() == DEFAULTS


def test_corrupted_storage_falls_back_to_defaults(tmp_path):
    broken = settings_mod.SettingsStore(storage=FakeStorage({"settings": {"theme": 123, "nope": 1}}))
    broken.fallback_file = tmp_path / "settings.json"
    assert broken.load() == DEFAULTS


def test_file_fallback_when_storage_missing(tmp_path):
    """plugin-storage 不可用时要能用文件兜底（且固定 LF 写入）"""
    file_store = settings_mod.SettingsStore(storage=None)
    file_store.fallback_file = tmp_path / "settings.json"
    file_store.save({"theme": "light"})
    assert json.loads(file_store.fallback_file.read_text(encoding="utf-8"))["theme"] == "light"
    assert b"\r\n" not in file_store.fallback_file.read_bytes()


def test_settings_page_contains_controls(store):
    html = page_mod.render_settings_page(store.load(), {"system": [("版本", "1.2.0")], "security": []},
                                        ["zh-CN", "en-US"])
    for marker in ('id="set-theme"', 'id="set-language"', 'id="set-auto"', 'id="set-interval"',
                   'id="settings-save"', 'id="settings-reset"', 'settings.js', 'settings-data'):
        assert marker in html, f"设置页缺少 {marker}"


def test_settings_page_payload_is_valid_json(store):
    html = page_mod.render_settings_page(store.load(), {"system": [], "security": []}, ["zh-CN"])
    raw = html.split('id="settings-data" type="application/json">', 1)[1].split("</script>", 1)[0]
    payload = json.loads(raw)
    assert payload["current"]["theme"] == "dark"
    assert "saved" in payload["text"]


def test_translate_helper_falls_back_without_i18n():
    """i18n 插件不可用时 tr() 必须回退到调用方给的中文，而不是抛异常"""
    from oss.plugin.translate import tr

    assert tr("webui.title", "系统设置") == "系统设置"
