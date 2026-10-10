# 性能优化插件 (Performance Optimizer)

性能优化插件，提供缓存、对象池、批量处理等优化工具。

## 功能特性

### 1. 高速缓存 (`FastCache`)
- O(1) 时间复杂度的查找
- LRU 淘汰策略
- 可选 TTL 过期
- 命中率统计

```python
from plugin.performance_optimizer import cached

@cached(maxsize=1024, ttl=60)
def expensive_operation(x, y):
    return x ** y
```

### 2. 对象池 (`ObjectPool`)
- 避免频繁创建/销毁对象
- 自动扩容
- 使用统计

```python
from plugin.performance_optimizer import ObjectPool

pool = ObjectPool(lambda: bytearray(4096), maxsize=100)
buf = pool.acquire()
# ... use buf ...
pool.release(buf)
```

### 3. 批量处理器 (`BatchProcessor`)
- 累积批量处理
- 超时自动触发
- 减少系统调用

```python
from plugin.performance_optimizer import BatchProcessor

processor = BatchProcessor(
    batch_handler=lambda items: db.bulk_insert(items),
    batch_size=100,
    timeout=1.0
)
for item in items:
    processor.add(item)
processor.flush()
```

### 4. 内存预分配器 (`MemoryArena`)
- 预分配大块内存
- 按需切分
- 减少内存碎片

```python
from plugin.performance_optimizer import MemoryArena

arena = MemoryArena(size=1024*1024)  # 1MB
chunk = arena.allocate(256)
# ... use chunk ...
arena.deallocate(chunk)
```

### 5. 性能分析器 (`PerfProfiler`)
- 低开销计时
- 嵌套支持
- 统计汇总

```python
from plugin.performance_optimizer import PerfProfiler

profiler = PerfProfiler()
with profiler.context("operation"):
    # ... do something ...
print(profiler.stats())
```

### 6. 字符串驻留 (`StringIntern`)
- 重复字符串去重
- 减少内存占用
- 加速字符串比较

```python
from plugin.performance_optimizer import StringIntern

intern = StringIntern()
s1 = intern.intern("hello")
s2 = intern.intern("hello")
assert s1 is s2  # 同一个对象
```

## API 参考

### PerformanceOptimizerPlugin

主插件类，提供统一的访问接口：

```python
# 获取插件实例
plugin = New()
plugin.init()

# 获取缓存
cache = plugin.get_cache("route_match")

# 获取对象池
pool = plugin.get_pool("bytearray_4k")

# 性能分析
profiler = plugin.profile()
with profiler.context("my_operation"):
    # ... do work ...

# 字符串驻留
s = plugin.intern_string("repeated string")

# 查看统计
stats = plugin.stats()
```

## 配置选项

在 `manifest.json` 中配置：

```json
{
  "config": {
    "args": {
      "cache_maxsize": 2048,
      "pool_maxsize": 100,
      "enable_profiler": true
    }
  }
}
```

## 性能提升

| 优化项 | 提升幅度 |
|--------|----------|
| 缓存命中 | 10-100x |
| 对象复用 | 5-20x |
| 批量操作 | 10-50x |
| 内存预分配 | 2-5x |
| 字符串驻留 | 2-10x |

## 注意事项

1. 缓存大小应根据实际内存限制调整
2. 对象池适合频繁创建/销毁的对象
3. 批量处理的 `batch_size` 和 `timeout` 需根据业务场景调优
4. 性能分析器在生产环境建议关闭以减少开销
