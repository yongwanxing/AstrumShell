# HTML 渲染服务

将存储在 plugin-storage 中的 HTML 页面映射到 8080 端口。

## 功能

- 从 plugin-storage 读取 HTML
- 自动注册路由到 web-toolkit
- 支持动态页面访问
- 页面管理（存储/获取/删除/列出）

## 使用

```python
html_render = plugin_mgr.get("html-render")

# 存储 HTML 页面
html_render.store_html("index", "<h1>Hello World</h1>")
html_render.store_html("about", "<h1>About</h1>")

# 获取页面
html = html_render.get_html("index")

# 列出所有页面
pages = html_render.list_pages()  # ["index", "about"]

# 删除页面
html_render.delete_page("about")
```

## 访问

```
http://localhost:8080/          → index 页面
http://localhost:8080/about     → about 页面
```

## 依赖

- web-toolkit：Web 服务
- plugin-storage：HTML 存储
