# plugin-bridge 插件桥接器

提供插件间的事件共享、广播、桥接和 RPC 服务调用。

## 功能

- **事件总线**: 插件间共享事件（发布/订阅）
- **广播**: 向多个插件发送消息
- **桥接**: 将不同插件的事件互相映射
- **RPC 服务调用**: 插件 A 调用插件 B 的方法并获取返回值

## 事件总线（发布/订阅 + 解耦）

```python
bridge = plugin_mgr.get("plugin-bridge")
bus = bridge.event_bus

# 订阅事件（发布者和订阅者解耦）
bus.on("http.request", lambda event: print(f"收到请求: {event.payload}"))

# 发布事件
bus.emit(BridgeEvent(
    type="http.request",
    source_plugin="http-api",
    payload={"path": "/api/users"}
))
```

## RPC 服务调用

```python
# 插件 B 注册服务
bridge.services.register("plugin-b", "get_user", lambda user_id: {"id": user_id, "name": "test"})

# 插件 A 调用插件 B 的服务
result = bridge.services.call("plugin-b", "get_user", 123)
print(result)  # {"id": 123, "name": "test"}
```

## 广播

```python
broadcast = bridge.broadcast

# 创建频道
broadcast.create_channel("system", ["lifecycle", "metrics"])

# 广播消息
broadcast.broadcast("system", {"action": "shutdown"}, "plugin-loader")
```

## 桥接

```python
bridge_mgr = bridge.bridge

# 创建桥接：将 http-api 的事件映射到 metrics
bridge_mgr.create_bridge(
    name="http-to-metrics",
    from_plugin="http-api",
    to_plugin="metrics",
    event_mapping={
        "http.request": "metrics.http_request",
        "http.error": "metrics.http_error",
    }
)
```

## 事件历史

```python
# 查询历史
history = bus.get_history("http.request")

# 清空历史
bus.clear_history()
```
