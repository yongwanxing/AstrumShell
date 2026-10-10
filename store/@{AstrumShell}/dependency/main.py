"""依赖解析插件 - 拓扑排序 + 循环依赖检测"""
from typing import Any, Optional

from oss.plugin.types import Plugin, register_plugin_type


class DependencyError(Exception):
    """依赖错误"""
    pass


class DependencyResolver:
    """依赖解析器"""

    def __init__(self):
        self.graph: dict[str, list[str]] = {}  # 插件名 -> 依赖列表

    def add_plugin(self, name: str, dependencies: list[str]):
        """添加插件及其依赖"""
        self.graph[name] = dependencies

    def resolve(self) -> list[str]:
        """解析依赖，返回拓扑排序后的插件列表
        
        例如：A 依赖 B，B 依赖 C
        图: A -> [B], B -> [C], C -> []
        结果: [C, B, A] (先启动没有依赖的，再启动依赖它们的)
        """
        # 检测循环依赖
        self._detect_cycles()

        # 拓扑排序 (Kahn 算法 - 反向)
        # in_degree[name] = name 依赖的插件数量
        in_degree: dict[str, int] = {name: 0 for name in self.graph}
        # 反向图: who_depends_on[dep] = [name1, name2, ...] (谁依赖 dep)
        who_depends_on: dict[str, list[str]] = {name: [] for name in self.graph}
        
        for name, deps in self.graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[name] += 1  # name 依赖 dep，所以 name 的入度 +1
                    who_depends_on[dep].append(name)  # dep 被 name 依赖

        # 从没有依赖的插件开始
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            # node 已启动，减少依赖它的插件的入度
            for dependent in who_depends_on.get(node, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self.graph):
            raise DependencyError("无法解析依赖，可能存在循环依赖")

        return result

    def _detect_cycles(self):
        """检测循环依赖"""
        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for dep in self.graph.get(node, []):
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    raise DependencyError(f"检测到循环依赖: {node} -> {dep}")

            rec_stack.remove(node)
            return False

        for node in self.graph:
            if node not in visited:
                if dfs(node):
                    raise DependencyError(f"检测到循环依赖涉及: {node}")

    def get_missing(self) -> list[str]:
        """获取缺失的依赖"""
        all_deps = set()
        for deps in self.graph.values():
            all_deps.update(deps)
        all_plugins = set(self.graph.keys())
        return list(all_deps - all_plugins)


class DependencyPlugin(Plugin):
    """依赖解析插件"""

    def __init__(self):
        self.resolver = DependencyResolver()
        self.plugin_deps: dict[str, list[str]] = {}

    def init(self, deps: dict = None):
        """初始化"""
        pass

    def start(self):
        """启动"""
        pass

    def stop(self):
        """停止"""
        pass

    def add_plugin(self, name: str, dependencies: list[str]):
        """添加插件及其依赖"""
        self.plugin_deps[name] = dependencies
        self.resolver.add_plugin(name, dependencies)

    def resolve(self) -> list[str]:
        """解析依赖顺序"""
        return self.resolver.resolve()

    def get_missing_deps(self) -> list[str]:
        """获取缺失的依赖"""
        return self.resolver.get_missing()

    def get_order(self) -> list[str]:
        """获取插件加载顺序"""
        return self.resolve()


# 注册类型
register_plugin_type("DependencyResolver", DependencyResolver)
register_plugin_type("DependencyError", DependencyError)


def New():
    return DependencyPlugin()
