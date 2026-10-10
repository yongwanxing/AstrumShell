"""共享路由工具函数"""
from typing import Callable, Optional, Any
from functools import lru_cache


class BaseRoute:
    """路由定义基类"""
    __slots__ = ('method', 'path', 'handler', '_pattern_parts')
    
    def __init__(self, method: str, path: str, handler: Callable):
        self.method = method
        self.path = path
        self.handler = handler
        # 预编译路径模式，避免重复解析
        self._pattern_parts = path.strip("/").split("/") if ":" in path else None


@lru_cache(maxsize=1024)
def match_path(pattern: str, path: str) -> bool:
    """路径匹配

    支持:
    - 精确匹配：/api/users == /api/users
    - 参数匹配：/api/users/:id 匹配 /api/users/123
    - 通配符匹配：/api/:path 匹配 /api/users/123/profile

    Args:
        pattern: 路由模式 (如 /api/users/:id)
        path: 实际请求路径 (如 /api/users/123)

    Returns:
        是否匹配成功
    """
    if pattern == path:
        return True
    
    pattern_parts = _get_pattern_parts(pattern)
    if pattern_parts is None:
        return False
    
    path_parts = path.strip("/").split("/")
    
    # 检查是否是通配符模式（最后一个参数以 : 开头且是通配符名称）
    last_pattern = pattern_parts[-1]
    is_wildcard = _is_wildcard_param(last_pattern)
    
    if is_wildcard and len(path_parts) >= len(pattern_parts):
        # 通配符模式：允许更多路径段
        for i, p in enumerate(pattern_parts[:-1]):
            if i >= len(path_parts):
                return False
            if not p.startswith(":") and p != path_parts[i]:
                return False
        return True
    
    # 普通参数匹配，段数必须相同
    if len(pattern_parts) != len(path_parts):
        return False
    
    for p, a in zip(pattern_parts, path_parts):
        if not p.startswith(":") and p != a:
            return False
    
    return True


def _is_wildcard_param(param: str) -> bool:
    """判断参数是否为通配符（如 :path, :wildcard 等）"""
    if not param.startswith(":"):
        return False
    name = param[1:].lower()
    # 常见的通配符参数名
    return name in ("path", "wildcard", "rest", "catch", "all")


@lru_cache(maxsize=512)
def _get_pattern_parts(pattern: str) -> Optional[list]:
    """获取并缓存路径模式的分割结果"""
    if ":" not in pattern:
        return None
    return pattern.strip("/").split("/")


@lru_cache(maxsize=1024)
def extract_path_params(pattern: str, path: str) -> dict[str, str]:
    """从路径中提取参数

    Args:
        pattern: 路由模式 (如 /api/users/:id)
        path: 实际请求路径 (如 /api/users/123)

    Returns:
        参数字典 (如 {"id": "123"})
    """
    params = {}
    
    pattern_parts = _get_pattern_parts(pattern)
    if pattern_parts is None:
        return params
    
    path_parts = path.strip("/").split("/")
    
    # 检查是否是通配符模式
    last_pattern = pattern_parts[-1]
    is_wildcard = _is_wildcard_param(last_pattern)
    use_wildcard = is_wildcard and len(path_parts) > len(pattern_parts)
    
    # 确定要迭代的模式部分数量
    if use_wildcard:
        # 通配符模式：只处理前面的固定部分
        parts_to_process = pattern_parts[:-1]
    else:
        # 普通模式：处理所有部分
        parts_to_process = pattern_parts
    
    for i, p in enumerate(parts_to_process):
        if i < len(path_parts) and p.startswith(":"):
            param_name = p[1:]  # 去掉 :
            params[param_name] = path_parts[i]
    
    # 处理通配符
    if use_wildcard:
        param_name = last_pattern[1:]
        # 将剩余的路径段合并
        remaining = "/".join(path_parts[len(pattern_parts) - 1:])
        params[param_name] = remaining
    
    return params


class BaseRouter:
    """路由器基类
    
    提供通用的路由注册和匹配功能，子类只需实现 handle() 方法
    """
    
    def __init__(self):
        self.routes: list[BaseRoute] = []
    
    def add(self, method: str, path: str, handler: Callable):
        """添加路由"""
        self.routes.append(BaseRoute(method, path, handler))
    
    def get(self, path: str, handler: Callable):
        """GET 路由"""
        self.add("GET", path, handler)
    
    def post(self, path: str, handler: Callable):
        """POST 路由"""
        self.add("POST", path, handler)
    
    def put(self, path: str, handler: Callable):
        """PUT 路由"""
        self.add("PUT", path, handler)
    
    def delete(self, path: str, handler: Callable):
        """DELETE 路由"""
        self.add("DELETE", path, handler)
    
    def find_route(self, method: str, path: str) -> Optional[tuple[BaseRoute, dict[str, str]]]:
        """查找匹配的路由和路径参数
        
        Args:
            method: HTTP 方法
            path: 请求路径
        
        Returns:
            (路由，路径参数) 或 None
        """
        for route in self.routes:
            if route.method == method and match_path(route.path, path):
                params = extract_path_params(route.path, path)
                return route, params
        return None
