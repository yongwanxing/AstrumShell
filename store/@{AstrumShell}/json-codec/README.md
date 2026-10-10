# json-codec JSON 编解码器

提供插件间 JSON 数据的编码、解码和验证功能。

## 功能

- **JSON 编码**: Python 对象 → JSON 字符串
- **JSON 解码**: JSON 字符串 → Python 对象
- **Schema 验证**: 验证 JSON 数据结构
- **自定义类型**: 支持注册自定义类型编解码器

## 基本使用

```python
codec = plugin_mgr.get("json-codec")

# 编码
data = {"name": "test", "count": 42}
json_str = codec.encode(data)
# '{"name": "test", "count": 42}'

# 编码（格式化）
json_pretty = codec.encode(data, pretty=True)
# '{\n  "name": "test",\n  "count": 42\n}'

# 解码
parsed = codec.decode(json_str)
# {"name": "test", "count": 42}
```

## HTTP 响应处理

```python
# 在 http-api 插件中使用
router.get("/api/users", lambda req: Response(
    status=200,
    headers={"Content-Type": "application/json"},
    body=codec.encode({"users": [...]})
))
```

## Schema 验证

```python
# 注册 schema
codec.register_schema("user", {
    "type": "object",
    "required": ["name", "email"],
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"},
        "age": {"type": "number"}
    }
})

# 验证数据
user_data = {"name": "test", "email": "test@example.com"}
is_valid = codec.validate(user_data, "user")
```

## 自定义类型

```python
from datetime import datetime

# 注册自定义编码器
codec.serializer.register_encoder(datetime, lambda dt: dt.isoformat())

# 使用
data = {"created_at": datetime.now()}
json_str = codec.encode(data)
```

## 错误处理

```python
from oss.plugin.types import JsonCodecError

try:
    result = codec.decode("invalid json")
except JsonCodecError as e:
    print(f"解码失败: {e}")
```
