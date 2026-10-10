"""i18n 核心引擎"""
import json
import re
from pathlib import Path
from typing import Any, Optional


class I18nEngine:
    """国际化引擎"""

    def __init__(self):
        self._translations: dict[str, dict[str, Any]] = {}  # {locale: {key: value}}
        self._current_locale: str = "zh-CN"
        self._fallback_locale: str = "en-US"
        self._supported_locales: list[str] = []
        self._locales_dir: str = ""

    def load_locales(self, locales_dir: str, locales: list[str]):
        """加载语言文件
        
        Args:
            locales_dir: 语言文件目录路径
            locales: 支持的语言列表
        """
        self._locales_dir = locales_dir
        self._supported_locales = locales
        locales_path = Path(locales_dir)
        
        if not locales_path.exists():
            locales_path.mkdir(parents=True, exist_ok=True)
            return

        for locale in locales:
            locale_file = locales_path / f"{locale}.json"
            if locale_file.exists():
                try:
                    content = locale_file.read_text(encoding="utf-8")
                    self._translations[locale] = json.loads(content)
                except (json.JSONDecodeError, Exception) as e:
                    print(f"[i18n] 加载语言文件失败 {locale_file}: {e}")
                    self._translations[locale] = {}

    def set_locale(self, locale: str):
        """设置当前语言"""
        if locale in self._supported_locales:
            self._current_locale = locale

    def get_locale(self) -> str:
        """获取当前语言"""
        return self._current_locale

    def set_fallback(self, locale: str):
        """设置回退语言"""
        self._fallback_locale = locale

    def t(self, key: str, locale: Optional[str] = None, **kwargs) -> str:
        """翻译文本
        
        Args:
            key: 翻译键 (支持点号分隔的嵌套路径，如 "user.greeting")
            locale: 指定语言 (默认使用当前语言)
            **kwargs: 插值参数
            
        Returns:
            翻译后的文本
        """
        target_locale = locale or self._current_locale
        
        # 尝试从指定语言获取
        value = self._get_nested(key, self._translations.get(target_locale, {}))
        
        # 如果未找到，尝试从回退语言获取
        if value is None and target_locale != self._fallback_locale:
            value = self._get_nested(key, self._translations.get(self._fallback_locale, {}))
        
        # 仍未找到，返回键名
        if value is None:
            return key
        
        # 插值处理: {{name}} 或 {name}
        return self._interpolate(value, kwargs)

    def _get_nested(self, key: str, data: dict) -> Any:
        """获取嵌套字典值"""
        keys = key.split(".")
        current = data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        return current

    def _interpolate(self, text: str, kwargs: dict) -> str:
        """插值替换: {{name}} 或 {name}"""
        # 支持 {{name}} 格式
        result = re.sub(r'\{\{(\w+)\}\}', lambda m: str(kwargs.get(m.group(1), m.group(0))), text)
        # 支持 {name} 格式 (如果未被 {{}} 替换)
        result = re.sub(r'\{(\w+)\}', lambda m: str(kwargs.get(m.group(1), m.group(0))), result)
        return result

    def get_supported_locales(self) -> list[str]:
        """获取支持的语言列表"""
        return self._supported_locales

    def is_valid_locale(self, locale: str) -> bool:
        """检查语言是否有效"""
        return locale in self._supported_locales

    def detect_locale(self, accept_language: Optional[str] = None, 
                     query_lang: Optional[str] = None,
                     cookie_lang: Optional[str] = None) -> str:
        """检测语言优先级
        
        Args:
            accept_language: HTTP Accept-Language 头
            query_lang: URL 查询参数 ?lang=xx
            cookie_lang: Cookie 中的语言
            
        Returns:
            检测到的语言代码
        """
        # 1. 查询参数优先级最高
        if query_lang and self.is_valid_locale(query_lang):
            return query_lang
        
        # 2. Cookie 次之
        if cookie_lang and self.is_valid_locale(cookie_lang):
            return cookie_lang
        
        # 3. Accept-Language 头
        if accept_language:
            # 解析 "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"
            languages = []
            for part in accept_language.split(","):
                part = part.strip()
                if ";q=" in part:
                    lang, q = part.split(";q=")
                    languages.append((lang.strip(), float(q)))
                else:
                    languages.append((part, 1.0))
            
            # 按权重排序
            languages.sort(key=lambda x: x[1], reverse=True)
            
            for lang, _ in languages:
                # 精确匹配
                if self.is_valid_locale(lang):
                    return lang
                # 前缀匹配 (zh 匹配 zh-CN, zh-TW)
                for supported in self._supported_locales:
                    if supported.startswith(lang + "-") or lang.startswith(supported.split("-")[0] + "-"):
                        return supported
        
        # 4. 默认语言
        return self._current_locale
