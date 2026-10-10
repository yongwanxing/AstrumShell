# web-toolkit Web 工具包

提供静态文件服务、模板渲染、路由等 Web 开发工具。

## 功能

- **静态文件服务**：提供 HTML/CSS/JS/图片等静态文件
- **模板引擎**：支持变量替换、条件判断、循环
- **路由管理**：为 HTTP 和 TCP 服务器注册路由
- **自动首页**：自动查找 index.html

## 使用

```python
web = plugin_mgr.get("web-toolkit")

# 设置目录
web.set_static_dir("./public")
web.set_template_dir("./templates")

# 添加自定义路由
web.add_route("GET", "/api/hello", lambda req: {
    "status": 200,
    "headers": {"Content-Type": "application/json"},
    "body": '{"message": "Hello"}'
})

# 渲染模板
html = web.render_template("page.html", {"title": "My Page", "items": [1, 2, 3]})
```

## 模板语法

```html
<!-- 变量 -->
<h1>{{ title }}</h1>
<p>{{ description }}</p>

<!-- 条件 -->
{% if show_content %}
  <div>{{ content }}</div>
{% endif %}

<!-- 循环 -->
<ul>
{% for item in items %}
  <li>{{ item }}</li>
{% endfor %}
</ul>
```

## 配置

```json
{
  "config": {
    "args": {
      "host": "0.0.0.0",
      "port": 8080,
      "static_dir": "./static",
      "template_dir": "./templates",
      "index_files": ["index.html", "index.htm"]
    }
  }
}
```

## 依赖

- http-api：HTTP 服务
- http-tcp：TCP HTTP 服务
