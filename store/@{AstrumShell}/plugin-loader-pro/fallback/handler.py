"""降级处理器"""
from typing import Callable, Any, Optional
from ..utils.logger import ProLogger


class FallbackStrategy:
    """降级策略枚举"""
    RETURN_DEFAULT = "return_default"
    RETURN_CACHE = "return_cache"
    RETURN_NULL = "return_null"
    CALL_ALTERNATIVE = "call_alternative"


class FallbackHandler:
    """降级处理器"""

    def __init__(self, strategy: str = FallbackStrategy.RETURN_NULL,
                 default_value: Any = None,
                 alternative_func: Callable = None):
        self.strategy = strategy
        self.default_value = default_value
        self.alternative_func = alternative_func
        self._cache = {}

    def execute(self, func: Callable, plugin_name: str, *args, **kwargs) -> Any:
        """执行降级逻辑"""
        try:
            result = func(*args, **kwargs)
            self._cache[plugin_name] = result
            return result
        except Exception as e:
            ProLogger.warn("fallback", f"插件 {plugin_name} 执行失败，触发降级: {type(e).__name__}: {e}")
            return self._apply_fallback(plugin_name)

    def _apply_fallback(self, plugin_name: str) -> Any:
        """应用降级策略"""
        if self.strategy == FallbackStrategy.RETURN_DEFAULT:
            return self.default_value
        elif self.strategy == FallbackStrategy.RETURN_CACHE:
            return self._cache.get(plugin_name)
        elif self.strategy == FallbackStrategy.RETURN_NULL:
            return None
        elif self.strategy == FallbackStrategy.CALL_ALTERNATIVE:
            if self.alternative_func:
                try:
                    return self.alternative_func()
                except Exception as e:
                    ProLogger.error("fallback", f"备选方案也失败了: {type(e).__name__}: {e}")
            return None
