# plugin-storage 插件存储

为所有插件提供隔离的键值存储服务。

## 功能

- **隔离存储**：每个插件有独立的命名空间
- **持久化**：数据自动保存到 JSON 文件
- **线程安全**：支持并发访问
- **共享访问**：通过 plugin-bridge 可跨插件访问

## 基本使用

```python
storage_plugin = plugin_mgr.get("plugin-storage")

# 获取插件的隔离存储
storage = storage_plugin.get_storage("my-plugin")

# 设置值
storage.set("key", "value")
storage.set("config", {"theme": "dark", "lang": "zh"})

# 获取值
value = storage.get("key")
config = storage.get("config", default={})

# 检查键
if storage.has("key"):
    print("存在")

# 删除
storage.delete("key")

# 批量设置
storage.set_many({"a": 1, "b": 2, "c": 3})

# 获取所有数据
all_data = storage.get_all()

# 清空
storage.clear()
```

## 通过 plugin-bridge 访问

```python
bridge = plugin_mgr.get("plugin-bridge")
shared_storage = bridge.storage  # 假设 bridge 集成了 storage

# 获取其他插件的存储（需要权限）
other_storage = shared_storage.get_plugin_storage("other-plugin")
data = other_storage.get("some_key")
```

## 存储位置

```
./data/storage/
├── plugin-a/
│   └── data.json
├── plugin-b/
│   └── data.json
└── ...
```

## 元信息

```python
meta = storage.get_meta()
# {"plugin": "my-plugin", "keys": 5, "path": "./data/storage/my-plugin"}
```
