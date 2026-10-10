"""i18n HTTP 中间件"""
import json
from typing import Optional, Callable
from oss.plugin.types import Response


class I18nMiddleware:
    """i18n 中间件
    
    自动检测语言并注入到请求上下文
    检测优先级:
    1. URL 查询参数 ?lang=xx
    2. Cookie locale=xx
    3. Accept-Language 头
    4. 默认语言
    """

    def __init__(self, engine, config: dict = None):
        self.engine = engine
        self.cookie_name = (config or {}).get("cookie_name", "locale")
        self.query_param = (config or {}).get("query_param", "lang")

    def handle(self, request: dict, next_fn: Callable) -> Response:
        """处理请求
        
        1. 检测语言
        2. 将语言注入到请求上下文
        3. 调用下一个中间件/处理器
        4. 可选: 在响应中添加 Content-Language 头
        """
        # 解析查询参数
        query_lang = self._parse_query_param(request.get("query", ""))
        
        # 解析 Cookie
        cookie_lang = self._parse_cookie(request.get("headers", {}))
        
        # 解析 Accept-Language
        accept_language = request.get("headers", {}).get("Accept-Language", 
                          request.get("headers", {}).get("accept-language", ""))
        
        # 检测语言
        locale = self.engine.detect_locale(
            accept_language=accept_language if accept_language else None,
            query_lang=query_lang,
            cookie_lang=cookie_lang
        )
        
        # 设置当前语言
        self.engine.set_locale(locale)
        
        # 注入到请求上下文
        request["locale"] = locale
        request["t"] = self.engine.t  # 提供翻译函数
        
        # 调用下一个处理器
        response = next_fn()
        
        # 在响应中添加 Content-Language 头
        if isinstance(response, Response):
            response.headers["Content-Language"] = locale
        
        return response

    def _parse_query_param(self, query_string: str) -> Optional[str]:
        """从查询字符串解析语言参数"""
        if not query_string:
            return None
        
        # 解析 ?lang=xx 或 &lang=xx
        params = {}
        for param in query_string.lstrip("?").split("&"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[key.strip()] = value.strip()
        
        return params.get(self.query_param)

    def _parse_cookie(self, headers: dict) -> Optional[str]:
        """从 Cookie 解析语言参数"""
        cookie_header = headers.get("Cookie", headers.get("cookie", ""))
        if not cookie_header:
            return None
        
        cookies = {}
        for cookie in cookie_header.split(";"):
            if "=" in cookie:
                key, value = cookie.split("=", 1)
                cookies[key.strip()] = value.strip()
        
        return cookies.get(self.cookie_name)
