"""WebUI - Web 控制台 (容器模式)"""
import json
import platform
import sys
import time
from pathlib import Path
from oss.logger.logger import Log
from oss.plugin.types import Plugin, Response, register_plugin_type
from oss.plugin.translate import tr, current_locale
from oss.config import get_config
from .core.server import WebUIServer
from .core.settings import SettingsStore, DEFAULTS
from .core.settings_page import render_settings_page


class WebUIPlugin(Plugin):
    """WebUI 插件 - 提供页面容器"""

    def __init__(self):
        self.http_api = None
        self.server = None
        self.config = {}
        self.storage = None              # plugin-storage 注入
        self.settings_store = None
        self.settings = dict(DEFAULTS)
        self._start_time = time.time()

    def meta(self):
        from oss.plugin.types import Metadata, PluginConfig, Manifest
        config = get_config()
        return Manifest(
            metadata=Metadata(
                name="webui",
                version="2.1.0",
                author="AstrumShell",
                description="Web 控制台容器 - 供其他插件注册页面"
            ),
            config=PluginConfig(
                enabled=True,
                args={
                    "port": config.get("HTTP_API_PORT", 8080),
                    "theme": "dark",
                    "title": "AstrumShell"
                }
            ),
            dependencies=["http-api"]
        )

    def set_http_api(self, http_api):
        """注入 http-api"""
        self.http_api = http_api

    def set_plugin_storage(self, storage):
        """注入 plugin-storage（设置持久化的首选存储）"""
        self.storage = storage

    def _get_storage(self):
        """取本插件专属的键值存储（plugin-storage 不可用时返回 None）"""
        if self.storage is None:
            return None
        try:
            return self.storage.get_storage("webui")
        except Exception as exc:
            Log.warn("webui", f"获取存储失败，将改用本地文件：{type(exc).__name__}: {exc}")
            return None

    # --- 设置 ---

    def get_settings(self) -> dict:
        """当前设置（供其他插件读取，例如仪表盘的刷新间隔）"""
        if self.settings_store is None:
            return dict(DEFAULTS)
        return self.settings_store.load()

    def save_settings(self, patch: dict) -> dict:
        """保存设置并立即生效（语言会同步给 i18n 引擎）"""
        if self.settings_store is None:
            raise RuntimeError("设置存储未初始化")
        data = self.settings_store.save(patch)
        self.settings = data
        self._apply_language(data.get("language"))
        return data

    def reset_settings(self) -> dict:
        if self.settings_store is None:
            raise RuntimeError("设置存储未初始化")
        data = self.settings_store.reset()
        self.settings = data
        self._apply_language(data.get("language"))
        return data

    def _apply_language(self, locale):
        """把语言设置同步给 i18n 引擎（让服务端渲染的文案跟着切换）"""
        if not locale:
            return
        try:
            from oss.plugin.runtime import get_plugin
            i18n = get_plugin("i18n")
            engine = getattr(i18n, "engine", None)
            if engine is not None and engine.is_valid_locale(locale):
                engine.set_locale(locale)
        except Exception as exc:
            Log.warn("webui", f"同步语言到 i18n 失败：{type(exc).__name__}: {exc}")

    def _supported_locales(self) -> list:
        try:
            from oss.plugin.runtime import get_plugin
            engine = getattr(get_plugin("i18n"), "engine", None)
            if engine is not None:
                return list(engine.get_supported_locales())
        except Exception:
            pass
        return []

    def init(self, deps: dict = None):
        """初始化 WebUI 服务器"""
        if not self.http_api:
            Log.error("webui", "错误: 未找到 http-api 依赖")
            return

        config = {}
        if deps:
            config = deps.get("config", {})

        self.config = {
            "port": config.get("port", get_config().get("HTTP_API_PORT", 8080)),
            "theme": config.get("theme", "dark"),
            "title": config.get("title", "AstrumShell")
        }

        # 使用 http-api 的路由器
        self.server = WebUIServer(
            self.http_api.router,
            self.config,
            settings_getter=self.get_settings,
            translator=tr,
        )

        # 设置存储（plugin-storage 优先，文件回退）与初始语言
        self.settings_store = SettingsStore(storage=self._get_storage(), plugin_name="webui")
        self.settings = self.settings_store.load()
        self._apply_language(self.settings.get("language"))
        Log.info("webui", "容器初始化完成")

    def start(self):
        """启动服务器（注册默认路由 + 设置页）"""
        if self.server:
            # 检测仪表盘是否已安装，自动设为首页
            self._setup_home_page()
            # 设置页 + 设置 API（齿轮按钮指向 /settings）
            self._register_settings()

            self.server.start()
            Log.info("webui", f"WebUI 容器已启动: http://localhost:{self.config['port']}")

    def _setup_home_page(self):
        """设置首页：如果仪表盘已安装则跳转到仪表盘，否则显示默认首页"""
        # 通过文件系统检查 dashboard 是否存在
        dashboard_exists = False
        store_dirs = [
            Path("store/@{AstrumShell}/dashboard"),
        ]
        for d in store_dirs:
            if d.exists() and (d / "main.py").exists():
                dashboard_exists = True
                break
        
        if dashboard_exists:
            # 仪表盘已安装，注册首页重定向到仪表盘
            self.server.router.get("/", self._handle_home_redirect)
            Log.info("webui", "检测到仪表盘，首页自动跳转到 /dashboard")
        else:
            # 默认首页
            self.server.register_page(
                path="/",
                content_provider=self.server._default_home_content,
                nav_item={'icon': 'ri-home-4-line', 'text': '首页'}
            )

    def _handle_home_redirect(self, request):
        """处理首页重定向到仪表盘"""
        return Response(
            status=302,
            headers={"Location": "/dashboard", "Content-Type": "text/html"},
            body=""
        )

    def _register_settings(self):
        """注册设置页与设置 API（齿轮按钮指向 /settings）"""
        self.server.register_page(path='/settings', content_provider=self._render_settings, nav_item=None)
        self.server.router.get("/api/settings", self._handle_settings_get)
        self.server.router.post("/api/settings", self._handle_settings_post)
        self.server.router.post("/api/settings/reset", self._handle_settings_reset)
        Log.info("webui", "设置页已注册：/settings")

    @staticmethod
    def _json(payload: dict, status: int = 200):
        return Response(
            status=status,
            headers={"Content-Type": "application/json; charset=utf-8"},
            body=json.dumps(payload, ensure_ascii=False),
        )

    def _handle_settings_get(self, request):
        """GET /api/settings → 当前设置 + 默认值 + 可选语言"""
        try:
            settings = self.get_settings()
        except Exception as exc:
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        return self._json({
            "settings": settings,
            "defaults": dict(DEFAULTS),
            "locales": self._supported_locales(),
        })

    def _handle_settings_post(self, request):
        """POST /api/settings → 保存设置（非法值返回 400）"""
        try:
            body = json.loads(request.body) if getattr(request, "body", "") else {}
        except json.JSONDecodeError as exc:
            return self._json({"error": f"请求体不是合法 JSON：{exc}"}, 400)
        if not isinstance(body, dict):
            return self._json({"error": "请求体必须是 JSON 对象"}, 400)

        language = body.get("language")
        if isinstance(language, str):
            locales = self._supported_locales()
            if locales and language not in locales:
                return self._json({"error": f"不支持的语言：{language}", "supported": locales}, 400)

        try:
            saved = self.save_settings(body)
        except ValueError as exc:
            return self._json({"error": str(exc)}, 400)
        except Exception as exc:
            return self._json({"error": f"保存失败：{type(exc).__name__}: {exc}"}, 500)

        Log.info("webui", f"设置已更新：{', '.join(sorted(body.keys()))}")
        return self._json({"message": tr("webui.saved", "设置已保存"), "settings": saved})

    def _handle_settings_reset(self, request):
        """POST /api/settings/reset → 恢复默认设置"""
        try:
            saved = self.reset_settings()
        except Exception as exc:
            return self._json({"error": f"重置失败：{type(exc).__name__}: {exc}"}, 500)
        Log.info("webui", "设置已恢复默认")
        return self._json({"message": tr("webui.saved", "已恢复默认设置"), "settings": saved})

    def _render_settings(self) -> str:
        """渲染设置页（i18n 文案 + 只读系统/安全信息）"""
        try:
            settings = self.get_settings()
        except Exception as exc:
            Log.warn("webui", f"读取设置失败，使用默认值：{type(exc).__name__}: {exc}")
            settings = dict(DEFAULTS)
        return render_settings_page(settings, self._collect_info(), self._supported_locales())

    def _collect_info(self) -> dict:
        """设置页里的只读信息：系统信息 + 安全状态"""
        config = get_config()
        try:
            from oss import __version__ as shell_version
        except Exception:
            shell_version = "?"

        plugin_count = "?"
        try:
            from oss.plugin.runtime import list_plugins
            names = list_plugins()
            if names:
                plugin_count = str(len(names))
        except Exception:
            pass

        system_rows = [
            (tr("webui.version", "版本"), f"AstrumShell {shell_version}"),
            (tr("webui.platform", "平台"), f"{platform.system()} {platform.release()}"),
            (tr("webui.python", "Python"), platform.python_version()),
            (tr("webui.data_dir", "数据目录"), str(Path(str(config.data_dir)).absolute())),
            (tr("webui.plugins_loaded", "已加载插件"), plugin_count),
            (tr("webui.uptime", "运行时间"), self._format_uptime(time.time() - self._start_time)),
        ]

        enforce = bool(config.get("ENFORCE_SIGNATURE", True))
        security_rows = [
            (tr("webui.enforce_signature", "强制插件签名校验"),
             tr("webui.on", "开") if enforce else tr("webui.off", "关")),
            (tr("webui.signature_anchor", "信任锚指纹"), self._anchor_fingerprint()),
        ]
        return {"system": system_rows, "security": security_rows}

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """紧凑运行时长，例如 ``3d 04:05:06``（不写中文，避免本地化文案里混语言）"""
        total = int(max(seconds, 0))
        days, rem = divmod(total, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        clock = f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{days}d {clock}" if days else clock

    @staticmethod
    def _anchor_fingerprint() -> str:
        """信任锚（AstrumShell 公钥）的 SHA-256 指纹，可与 tools/update_trust_anchors.py 对照"""
        try:
            import hashlib
            from cryptography.hazmat.primitives import serialization
            from oss.plugin.runtime import get_plugin

            verifier = getattr(get_plugin("signature-verifier"), "verifier", None)
            pem = (getattr(verifier, "public_keys", None) or {}).get("AstrumShell")
            if not pem:
                return tr("webui.unknown", "未知")
            key = serialization.load_pem_public_key(pem)
            der = key.public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            digest = hashlib.sha256(der).hexdigest().upper()
            return ":".join(digest[i:i + 4] for i in range(0, 20, 4)) + "…"
        except Exception:
            return tr("webui.unknown", "未知")

    def stop(self):
        Log.info("webui", "WebUI 容器已停止")

    # --- 公开 API 供其他插件调用 ---

    def register_page(self, path: str, content_provider, nav_item: dict = None):
        """
        其他插件调用此方法注册页面。
        :param path: 路由路径 (e.g., '/dashboard')
        :param content_provider: 无参函数，返回 HTML 字符串
        :param nav_item: 导航项 {'icon': '📊', 'text': '仪表盘'}
        """
        if self.server:
            self.server.register_page(path, content_provider, nav_item)
        else:
            Log.warn("webui", f"警告: 试图注册页面 {path}，但服务器未初始化")

    def add_nav_item(self, item: dict):
        """仅添加导航项（如果页面由其他方式处理）"""
        if self.server:
            self.server.nav_items.append(item)


register_plugin_type("WebUIPlugin", WebUIPlugin)


def New():
    return WebUIPlugin()
