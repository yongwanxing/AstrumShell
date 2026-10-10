# hot-reload 热插拔

运行时加载、卸载、更新插件，无需重启服务。

## 功能

- 运行时加载新插件
- 运行时卸载插件
- 运行时更新插件（热重载）
- 自动监听文件变化（可选）
- 模块缓存清理

## 使用

```python
from pathlib import Path

# 加载新插件
hot_reload.load_plugin(Path("store/@{Author/new-plugin"))

# 卸载插件
hot_reload.unload_plugin("plugin-name")

# 更新插件
hot_reload.reload_plugin("plugin-name", Path("store/@{Author/plugin-name"))
```

## 注意事项

- 插件必须实现 `init()`, `start()`, `stop()`
- 卸载时会调用 `stop()`
- 更新时先 `stop()` 再 `init()` + `start()`
