# lifecycle 生命周期管理

管理插件的状态转换和钩子函数。

## 功能

- 状态机：`pending` → `running` → `stopped`
- 支持状态转换验证
- 提供生命周期钩子：
  - `before_start`
  - `after_start`
  - `before_stop`
  - `after_stop`
- 支持扩展能力注入

## 状态转换

```
pending → running → stopped
              ↕
          (可重启)
```

## 使用

```python
lc = lifecycle_plugin.create("my-plugin")
lc.on("after_start", lambda: print("started"))
lc.start()
```
