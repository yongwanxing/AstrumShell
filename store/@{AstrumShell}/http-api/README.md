# http-api HTTP API 服务

提供 HTTP RESTful API 服务，支持路由、中间件等功能。

## 功能

- HTTP 服务器（GET/POST/PUT/DELETE）
- 路由匹配（支持参数路由 `:id`）
- 中间件链（CORS/日志/限流）
- 分散式布局（每个文件 < 200 行）

## 路由使用

```python
# 在插件中获取 router
http_plugin = plugin_mgr.get("http-api")
router = http_plugin.router

# 添加路由
router.get("/health", lambda req: Response(status=200, body='{"status": "ok"}'))
router.get("/api/users", handle_users)
router.post("/api/users", handle_create_user)
router.get("/api/users/:id", handle_user_by_id)
```

## 中间件

```python
middleware = http_plugin.middleware

# 添加自定义中间件
class MyMiddleware(Middleware):
    def process(self, ctx, next_fn):
        # 前置处理
        resp = next_fn()  # 继续执行
        # 后置处理
        return resp

middleware.add(MyMiddleware())
```

## 配置

```json
{
  "config": {
    "args": {
      "host": "0.0.0.0",
      "port": 8080
    }
  }
}
```
