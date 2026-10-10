# http-tcp HTTP TCP 服务

提供基于 TCP 的 HTTP 协议实现。

## 功能

- 原始 TCP HTTP 服务器
- 路由匹配
- 中间件链（日志/CORS）
- 连接管理
- 事件发布（通过 plugin-bridge）

## 使用

```python
tcp = plugin_mgr.get("http-tcp")

# 注册路由
tcp.router.get("/api/status", lambda req: {
    "status": 200,
    "headers": {"Content-Type": "application/json"},
    "body": '{"status": "ok"}'
})

# 获取客户端
clients = tcp.server.get_clients()
```

## 事件

```python
bridge = plugin_mgr.get("plugin-bridge")
bus = bridge.event_bus

bus.on("tcp.connect", lambda e: print(f"连接: {e.client.id}"))
bus.on("tcp.http.request", lambda e: print(f"请求: {e.context['request']['path']}"))
bus.on("tcp.disconnect", lambda e: print(f"断开: {e.client.id}"))
```

## 配置

```json
{
  "config": {
    "args": {
      "host": "0.0.0.0",
      "port": 8082
    }
  }
}
```
