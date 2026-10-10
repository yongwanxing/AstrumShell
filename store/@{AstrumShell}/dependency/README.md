# dependency 依赖解析

插件依赖关系管理，使用拓扑排序确定加载顺序。

## 功能

- 拓扑排序（Kahn 算法）
- 循环依赖检测（DFS）
- 缺失依赖检测
- 自动按依赖顺序加载插件

## 使用

```python
dep = dependency_plugin

# 添加插件及其依赖
dep.add_plugin("plugin-a", ["plugin-b", "plugin-c"])
dep.add_plugin("plugin-b", [])
dep.add_plugin("plugin-c", ["plugin-b"])

# 解析依赖顺序
order = dep.resolve()  # 返回 ["plugin-b", "plugin-c", "plugin-a"]

# 检查缺失依赖
missing = dep.get_missing_deps()

# 获取加载顺序
order = dep.get_order()
```

## manifest.json 声明

```json
{
  "metadata": {...},
  "dependencies": ["lifecycle", "circuit-breaker"]
}
```
