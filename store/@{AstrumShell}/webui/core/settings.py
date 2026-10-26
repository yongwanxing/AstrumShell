"""WebUI 设置：持久化 + 校验 + 应用

存储优先级：

1. **plugin-storage**（项目推荐的统一文件读写入口 → ``data/webui/data.json``）
2. 回退：``data/webui/settings.json``（plugin-storage 不可用时自建文件）

所有设置项都有默认值；写入时逐项校验，非法值会被拒绝（不会把配置写坏）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from oss.config import get_config
from oss.logger.logger import Log

#: 支持的设置项与默认值（键名会被前端与 /api/settings 直接使用）
DEFAULTS: dict[str, Any] = {
    "theme": "dark",                       # light | dark
    "language": "zh-CN",                   # 由 i18n 引擎校验
    "dashboard_auto_refresh": True,
    "dashboard_refresh_interval": 2,       # 秒，1..60
}

THEMES = ("light", "dark")
MIN_INTERVAL, MAX_INTERVAL = 1, 60
_TRUE = ("true", "1", "yes", "on")
_FALSE = ("false", "0", "no", "off")


def coerce(key: str, value: Any) -> Optional[Any]:
    """按默认值类型校验并转换；非法返回 ``None``"""
    default = DEFAULTS[key]

    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in _TRUE:
                return True
            if text in _FALSE:
                return False
        return None

    if isinstance(default, int):
        if isinstance(value, bool):
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        if key == "dashboard_refresh_interval" and not (MIN_INTERVAL <= number <= MAX_INTERVAL):
            return None
        return number

    if isinstance(default, str):
        if not isinstance(value, str):
            return None
        text = value.strip()
        return text or None

    return None


class SettingsStore:
    """设置存取（plugin-storage 优先，文件回退）"""

    def __init__(self, storage: Optional[Any] = None, plugin_name: str = "webui"):
        self.plugin_name = plugin_name
        self.storage = storage
        self.fallback_file = Path(str(get_config().data_dir)) / plugin_name / "settings.json"

    # ---------- 公开 API ----------

    def load(self) -> dict[str, Any]:
        """读取设置（缺失/损坏的项自动回落到默认值）"""
        raw = self._load_raw()
        data = dict(DEFAULTS)
        if isinstance(raw, dict):
            for key, value in raw.items():
                if key not in DEFAULTS:
                    continue
                coerced = coerce(key, value)
                if coerced is not None:
                    data[key] = coerced
        return data

    def save(self, patch: dict[str, Any]) -> dict[str, Any]:
        """局部更新设置，返回完整设置；非法值抛 ``ValueError``"""
        if not isinstance(patch, dict):
            raise ValueError("设置必须是 JSON 对象")
        data = self.load()
        unknown = [key for key in patch if key not in DEFAULTS]
        if unknown:
            raise ValueError(f"未知设置项: {', '.join(unknown)}")
        for key, value in patch.items():
            coerced = coerce(key, value)
            if coerced is None:
                raise ValueError(f"设置项 {key} 的值非法: {value!r}")
            if key == "theme" and coerced not in THEMES:
                raise ValueError(f"主题只能是 {' / '.join(THEMES)}")
            data[key] = coerced
        self._persist(data)
        return data

    def reset(self) -> dict[str, Any]:
        """恢复默认设置"""
        data = dict(DEFAULTS)
        self._persist(data)
        return data

    # ---------- 内部 ----------

    def _load_raw(self) -> Optional[dict]:
        if self.storage is not None:
            try:
                raw = self.storage.get("settings", None)
                if isinstance(raw, dict):
                    return raw
            except Exception as exc:
                Log.warn("webui", f"读取设置失败（plugin-storage）：{type(exc).__name__}: {exc}")
        try:
            if self.fallback_file.exists():
                return json.loads(self.fallback_file.read_text(encoding="utf-8"))
        except Exception as exc:
            Log.warn("webui", f"读取设置失败（{self.fallback_file}）：{type(exc).__name__}: {exc}")
        return None

    def _persist(self, data: dict[str, Any]) -> None:
        if self.storage is not None:
            try:
                self.storage.set("settings", data)
                return
            except Exception as exc:
                Log.warn("webui", f"写入设置失败（plugin-storage），改用文件：{type(exc).__name__}: {exc}")
        try:
            self.fallback_file.parent.mkdir(parents=True, exist_ok=True)
            self.fallback_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
                newline="\n",
            )
        except Exception as exc:
            Log.error("webui", f"写入设置失败（{self.fallback_file}）：{type(exc).__name__}: {exc}")
            raise
