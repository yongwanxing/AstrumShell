# ws-api WebSocket API

提供 WebSocket 实时双向通信服务。

## 功能

- WebSocket 服务器
- 路由匹配
- 中间件链（认证/日志）
- 广播消息
- 连接/断开/消息事件
- 与 HTTP 插件集成

## 使用

```python
ws = plugin_mgr.get("ws-api")

# 注册消息路由
ws.router.on_message("/chat", lambda client, msg: client.send({"echo": msg}))

# 广播
ws.server.broadcast({"type": "announcement", "data": "服务器维护通知"})

# 获取客户端列表
clients = ws.server.get_clients()
```

## 事件

```python
# 通过 plugin-bridge 订阅 WS 事件
bridge = plugin_mgr.get("plugin-bridge")
bridge.event_bus.on("ws.connect", lambda event: print(f"新连接: {event.client.path}"))
bridge.event_bus.on("ws.message", lambda event: print(f"消息: {event.message}"))
bridge.event_bus.on("ws.disconnect", lambda event: print(f"断开: {event.client.id}"))
```

## 配置

```json
{
  "config": {
    "args": {
      "host": "0.0.0.0",
      "port": 8081
    }
  }
}
```
