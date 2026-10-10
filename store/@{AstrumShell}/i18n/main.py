"""i18n 国际化多语言支持插件"""
import json
from pathlib import Path
from oss.logger.logger import Log
from oss.plugin.types import Plugin, register_plugin_type
from .i18n import I18nEngine
from .middleware import I18nMiddleware


class I18nPlugin(Plugin):
    """i18n 国际化插件"""

    def __init__(self):
        self.engine = I18nEngine()
        self.middleware_handler = None

    def meta(self):
        """插件元数据"""
        from oss.plugin.types import Metadata, PluginConfig, Manifest
        return Manifest(
            metadata=Metadata(
                name="i18n",
                version="1.0.0",
                author="AstrumShell",
                description="国际化多语言支持 - 提供翻译加载/语言切换/HTTP中间件"
            ),
            config=PluginConfig(
                enabled=True,
                args={
                    "default_locale": "zh-CN",
                    "fallback_locale": "en-US",
                    "supported_locales": ["zh-CN", "en-US", "zh-TW"]
                }
            ),
            dependencies=[]
        )

    def init(self, deps: dict = None):
        """初始化插件
        
        加载语言文件并初始化中间件
        """
        # 获取插件配置
        config = {}
        if deps:
            config = deps.get("config", {})
        
        # 默认配置
        default_locale = config.get("default_locale", "zh-CN")
        fallback_locale = config.get("fallback_locale", "en-US")
        supported_locales = config.get("supported_locales", ["zh-CN", "en-US", "zh-TW"])
        locales_dir = config.get("locales_dir", "locales")
        
        # 解析 locales_dir 相对路径
        plugin_dir = Path(__file__).parent
        full_locales_dir = plugin_dir / locales_dir
        
        # 设置回退语言
        self.engine.set_fallback(fallback_locale)
        
        # 加载语言文件
        self.engine.load_locales(str(full_locales_dir), supported_locales)
        
        # 设置默认语言
        self.engine.set_locale(default_locale)
        
        # 初始化中间件
        self.middleware_handler = I18nMiddleware(self.engine, config)
        
        Log.info("i18n", f"已加载语言: {', '.join(supported_locales)}")
        Log.info("i18n", f"默认语言: {default_locale}")

    def start(self):
        """启动插件
        
        注册 API 路由（如果有 http-api 依赖）
        """
        # 如果有 http-api 依赖，注册 i18n 相关路由
        http_api = None
        if hasattr(self, 'set_http_api'):
            http_api = getattr(self, '_http_api', None)
        
        if http_api and hasattr(http_api, 'router'):
            http_api.router.get("/api/i18n/locales", self._locales_handler)
            http_api.router.get("/api/i18n/translate", self._translate_handler)
            http_api.router.post("/api/i18n/locale", self._change_locale_handler)
            Log.info("i18n", "API 路由已注册")

    def stop(self):
        """停止插件"""
        Log.error("i18n", "插件已停止")

    def health(self) -> bool:
        """健康检查"""
        return self.engine is not None

    def stats(self) -> dict:
        """获取插件统计"""
        return {
            "current_locale": self.engine.get_locale(),
            "supported_locales": self.engine.get_supported_locales(),
            "loaded_translations": len(self.engine._translations)
        }

    # ========== 依赖注入 Setter ==========
    
    def set_http_api(self, http_api):
        """注入 http-api 依赖"""
        self._http_api = http_api

    # ========== API 处理器 ==========

    def _locales_handler(self, request):
        """获取支持的语言列表"""
        from oss.plugin.types import Response
        t = getattr(request, 't', self.engine.t)
        
        locales = []
        for locale in self.engine.get_supported_locales():
            locales.append({
                "code": locale,
                "name": t(f"plugin.i18n_name", locale=locale)
            })
        
        return Response(
            status=200,
            body=json.dumps({
                "current": self.engine.get_locale(),
                "supported": locales
            }),
            headers={"Content-Type": "application/json"}
        )

    def _translate_handler(self, request):
        """翻译接口
        
        GET /api/i18n/translate?key=user.greeting&locale=en-US&name=World
        """
        from oss.plugin.types import Response
        t = getattr(request, 't', self.engine.t)
        
        # 解析查询参数
        query = request.path.split("?", 1)[-1] if "?" in request.path else ""
        params = {}
        for param in query.split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[key] = value
        
        key = params.get("key", "")
        locale = params.get("locale", None)
        
        if not key:
            return Response(
                status=400,
                body=json.dumps({"error": t("api.missing_param", param="key")}),
                headers={"Content-Type": "application/json"}
            )
        
        # 翻译
        result = t(key, locale=locale, **params)
        
        return Response(
            status=200,
            body=json.dumps({
                "key": key,
                "locale": locale or self.engine.get_locale(),
                "text": result
            }),
            headers={"Content-Type": "application/json"}
        )

    def _change_locale_handler(self, request):
        """切换语言接口
        
        POST /api/i18n/locale
        Body: {"locale": "en-US"}
        """
        from oss.plugin.types import Response
        t = getattr(request, 't', self.engine.t)
        
        try:
            body = json.loads(request.body) if hasattr(request, 'body') and request.body else {}
        except json.JSONDecodeError:
            body = {}
        
        new_locale = body.get("locale", "")
        
        if not new_locale:
            return Response(
                status=400,
                body=json.dumps({"error": t("api.missing_param", param="locale")}),
                headers={"Content-Type": "application/json"}
            )
        
        if not self.engine.is_valid_locale(new_locale):
            return Response(
                status=400,
                body=json.dumps({"error": t("plugin.locale_not_supported", locale=new_locale)}),
                headers={"Content-Type": "application/json"}
            )
        
        self.engine.set_locale(new_locale)
        
        return Response(
            status=200,
            body=json.dumps({"message": t("plugin.locale_changed", locale=new_locale)}),
            headers={"Content-Type": "application/json"}
        )


register_plugin_type("I18nPlugin", I18nPlugin)


def New():
    return I18nPlugin()
