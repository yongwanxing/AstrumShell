"""插件侧翻译辅助

插件在渲染 HTML / 返回文本时经常需要翻译，但又不想强依赖 i18n 插件
（依赖成环、或 i18n 未安装）。这里通过运行时定位器找到 i18n 引擎，
取不到时安全回退到调用方给的默认文案。

    from oss.plugin.translate import tr
    tr("dashboard.title", "系统仪表盘")
"""

from __future__ import annotations

from typing import Any, Optional


def _engine() -> Optional[Any]:
    try:
        from oss.plugin.runtime import get_plugin
        plugin = get_plugin("i18n")
    except Exception:
        return None
    if plugin is None:
        return None
    return getattr(plugin, "engine", None)


def tr(key: str, fallback: Optional[str] = None, **kwargs: Any) -> str:
    """翻译 ``key``；i18n 不可用或未命中时返回 ``fallback``（默认返回 key 本身）"""
    engine = _engine()
    if engine is not None:
        try:
            text = engine.t(key, **kwargs)
            if text and text != key:
                return text
        except Exception:
            pass
    if fallback is None:
        return key
    # 回退文案里也做一次简单插值，保证 {{count}} 之类占位能替换
    for name, value in kwargs.items():
        fallback = fallback.replace("{{" + str(name) + "}}", str(value))
    return fallback


def current_locale(default: str = "zh-CN") -> str:
    """当前语言代码"""
    engine = _engine()
    if engine is not None:
        try:
            return engine.get_locale()
        except Exception:
            pass
    return default
