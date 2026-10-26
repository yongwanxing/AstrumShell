"""设置页渲染（HTML 片段，注入 WebUI 布局）

纯服务端渲染 + 静态 JS（``/static/js/settings.js``）：无框架依赖。
所有文案走 i18n（``oss.plugin.translate.tr``），i18n 不可用时回落中文。
"""

from __future__ import annotations

import json
from typing import Any

from oss.plugin.translate import tr


def _escape(value: Any) -> str:
    text = "" if value is None else str(value)
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;").replace("'", "&#39;"))


def _options(values: list[str], selected: str, labels: dict[str, str] | None = None) -> str:
    labels = labels or {}
    return "".join(
        f'<option value="{_escape(v)}"{" selected" if v == selected else ""}>'
        f'{_escape(labels.get(v, v))}</option>'
        for v in values
    )


def _fields(rows: list[tuple[str, str]]) -> str:
    return "".join(
        f'<div class="field"><span class="field-key">{_escape(k)}</span>'
        f'<span class="field-val">{_escape(v)}</span></div>'
        for k, v in rows
    )


def render_settings_page(settings: dict[str, Any], info: dict[str, Any], locales: list[str]) -> str:
    """渲染设置页片段

    :param settings: 当前设置（``core.settings.SettingsStore.load()``）
    :param info: 只读信息 ``{"system": [(标签, 值), ...], "security": [(标签, 值), ...]}``
    :param locales: 可选语言（来自 i18n 引擎；为空时只显示当前语言）
    """
    theme = settings.get("theme", "dark")
    language = settings.get("language", "zh-CN")
    auto_refresh = bool(settings.get("dashboard_auto_refresh", True))
    interval = settings.get("dashboard_refresh_interval", 2)

    theme_labels = {"light": tr("webui.theme_light", "浅色"), "dark": tr("webui.theme_dark", "深色")}
    locale_labels = {"zh-CN": "简体中文", "zh-TW": "繁體中文", "en-US": "English"}

    data = {
        "current": {
            "theme": theme, "language": language,
            "dashboard_auto_refresh": auto_refresh,
            "dashboard_refresh_interval": interval,
        },
        "text": {
            "saved": tr("webui.saved", "设置已保存"),
            "save_failed": tr("webui.save_failed", "保存失败：{{error}}"),
            "saving": tr("common.loading", "加载中..."),
            "interval_range": "1 - 60",
        },
    }
    # 用 <script type="application/json"> 传数据，避免在 HTML 里拼 JS 字符串
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    return f"""
<div class="page settings-page">
    <header class="page-head">
        <h1><i class="ri-settings-3-line"></i> {_escape(tr("webui.title", "系统设置"))}</h1>
        <p class="page-sub">{_escape(tr("webui.subtitle", "这些设置会被保存，重启后依然生效"))}</p>
    </header>

    <section class="panel">
        <h2>{_escape(tr("webui.appearance", "外观"))}</h2>
        <div class="form-row">
            <label for="set-theme">{_escape(tr("webui.theme", "主题"))}</label>
            <select id="set-theme" class="input">{_options(list(theme_labels), theme, theme_labels)}</select>
        </div>
    </section>

    <section class="panel">
        <h2>{_escape(tr("webui.language", "语言"))}</h2>
        <div class="form-row">
            <label for="set-language">{_escape(tr("webui.language", "语言"))}</label>
            <select id="set-language" class="input">{_options(locales or [language], language, locale_labels)}</select>
        </div>
    </section>

    <section class="panel">
        <h2>{_escape(tr("webui.dashboard", "仪表盘"))}</h2>
        <div class="form-row">
            <label for="set-auto">{_escape(tr("webui.auto_refresh", "自动刷新"))}</label>
            <label class="switch">
                <input type="checkbox" id="set-auto"{" checked" if auto_refresh else ""}>
                <span class="slider"></span>
            </label>
        </div>
        <div class="form-row">
            <label for="set-interval">{_escape(tr("webui.refresh_interval", "刷新间隔"))}</label>
            <input type="number" id="set-interval" class="input" min="1" max="60" step="1" value="{_escape(interval)}">
            <span class="hint">{_escape(tr("webui.seconds", "秒"))}</span>
        </div>
    </section>

    <div class="actions">
        <button type="button" id="settings-save" class="btn btn-primary">{_escape(tr("webui.save", "保存设置"))}</button>
        <button type="button" id="settings-reset" class="btn">{_escape(tr("webui.reset", "恢复默认"))}</button>
        <span id="settings-status" class="status"></span>
    </div>

    <section class="panel">
        <h2>{_escape(tr("webui.system_info", "系统信息"))}</h2>
        <div class="kv">{_fields(info.get("system", []))}</div>
    </section>

    <section class="panel">
        <h2>{_escape(tr("webui.security", "安全"))}</h2>
        <div class="kv">{_fields(info.get("security", []))}</div>
    </section>
</div>
<script id="settings-data" type="application/json">{payload}</script>
<script src="/static/js/settings.js" defer></script>
"""
