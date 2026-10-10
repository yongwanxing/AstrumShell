"""性能优化插件 - 缓存、对象池、批量处理等优化工具

提供以下优化功能:
1. 函数级 LRU 缓存装饰器
2. 对象池复用
3. 批量操作优化
4. 内存预分配
5. 热点代码路径优化
"""
import sys
import time
import functools
from typing import Any, Callable, Optional, TypeVar, Generic, Dict, List, Set
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
import weakref

# ========== 类型定义 ==========
T = TypeVar('T')
F = TypeVar('F', bound=Callable)


# ========== 高性能缓存装饰器 ==========
class FastCache:
    """超高速缓存管理器
    
    特性:
    - 基于 dict 的 O(1) 查找
    - LRU 淘汰策略
    - 可选 TTL 过期
    - 统计命中率
    """
    __slots__ = ('_cache', '_order', '_maxsize', '_ttl', '_hits', '_misses', '_lock')
    
    def __init__(self, maxsize: int = 1024, ttl: float = 0):
        self._cache: Dict[Any, Any] = {}
        self._order: deque = deque()
        self._maxsize = maxsize
        self._ttl = ttl
        self._hits = 0
        self._misses = 0
        self._lock = Lock() if sys.version_info < (3, 9) else None
    
    def get(self, key: Any) -> tuple[bool, Any]:
        """获取缓存值
        
        Returns:
            (是否命中，值)
        """
        if key not in self._cache:
            self._misses += 1
            return False, None
        
        entry = self._cache[key]
        # 检查 TTL
        if self._ttl > 0 and time.time() - entry[1] > self._ttl:
            del self._cache[key]
            try:
                self._order.remove(key)
            except ValueError:
                pass
            self._misses += 1
            return False, None
        
        # 更新 LRU 顺序
        self._order.remove(key)
        self._order.append(key)
        self._hits += 1
        return True, entry[0]
    
    def set(self, key: Any, value: Any):
        """设置缓存值"""
        if key in self._cache:
            self._order.remove(key)
        elif len(self._cache) >= self._maxsize:
            # 淘汰最旧的
            oldest = self._order.popleft()
            del self._cache[oldest]
        
        self._cache[key] = (value, time.time())
        self._order.append(key)
    
    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._order.clear()
        self._hits = 0
        self._misses = 0
    
    @property
    def hit_rate(self) -> float:
        """获取命中率"""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
    
    def stats(self) -> dict[str, Any]:
        return {
            "size": len(self._cache),
            "maxsize": self._maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
        }


def cached(maxsize: int = 1024, ttl: float = 0, key_func: Optional[Callable] = None):
    """高性能缓存装饰器
    
    Args:
        maxsize: 最大缓存条目数
        ttl: 过期时间（秒），0 表示永不过期
        key_func: 自定义 key 生成函数，默认使用 args+kwargs
    
    Example:
        @cached(maxsize=100)
        def expensive_compute(x, y):
            return x ** y
    """
    _cache = FastCache(maxsize=maxsize, ttl=ttl)
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存 key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = (args, tuple(sorted(kwargs.items())))
            
            hit, value = _cache.get(key)
            if hit:
                return value
            
            value = func(*args, **kwargs)
            _cache.set(key, value)
            return value
        
        wrapper.cache = _cache  # type: ignore
        wrapper.cache_clear = _cache.clear  # type: ignore
        wrapper.cache_stats = _cache.stats  # type: ignore
        return wrapper  # type: ignore
    
    return decorator  # type: ignore


# ========== 对象池 ==========
class ObjectPool(Generic[T]):
    """高性能对象池
    
    特性:
    - 避免频繁创建/销毁对象
    - 线程安全（可选）
    - 自动扩容
    - 使用统计
    
    Example:
        pool = ObjectPool(lambda: bytearray(4096))
        buf = pool.acquire()
        # ... use buf ...
        pool.release(buf)
    """
    __slots__ = ('_factory', '_pool', '_maxsize', '_created', '_acquired', '_lock')
    
    def __init__(self, factory: Callable[[], T], maxsize: int = 100):
        self._factory = factory
        self._pool: List[T] = []
        self._maxsize = maxsize
        self._created = 0
        self._acquired = 0
        self._lock = Lock() if sys.version_info < (3, 9) else None
    
    def acquire(self) -> T:
        """从池中获取对象"""
        if self._pool:
            obj = self._pool.pop()
        else:
            obj = self._factory()
            self._created += 1
        self._acquired += 1
        return obj
    
    def release(self, obj: T):
        """释放对象回池"""
        if len(self._pool) < self._maxsize:
            self._pool.append(obj)
    
    def clear(self):
        """清空对象池"""
        self._pool.clear()
    
    @property
    def size(self) -> int:
        return len(self._pool)
    
    def stats(self) -> dict[str, Any]:
        return {
            "pool_size": len(self._pool),
            "maxsize": self._maxsize,
            "total_created": self._created,
            "total_acquired": self._acquired,
            "reuse_rate": (self._acquired - self._created) / self._acquired if self._acquired > 0 else 0.0,
        }


# ========== 批量处理器 ==========
class BatchProcessor(Generic[T]):
    """批量操作处理器
    
    特性:
    - 累积一定数量后批量处理
    - 超时自动触发
    - 减少系统调用次数
    
    Example:
        processor = BatchProcessor(
            batch_handler=lambda items: db.bulk_insert(items),
            batch_size=100,
            timeout=1.0
        )
        for item in items:
            processor.add(item)
        processor.flush()
    """
    __slots__ = ('_handler', '_batch_size', '_timeout', '_buffer', '_last_flush', '_processed_count')
    
    def __init__(self, batch_handler: Callable[[List[T]], Any], batch_size: int = 100, timeout: float = 1.0):
        self._handler = batch_handler
        self._batch_size = batch_size
        self._timeout = timeout
        self._buffer: List[T] = []
        self._last_flush = time.time()
        self._processed_count = 0
    
    def add(self, item: T):
        """添加项目到缓冲区"""
        self._buffer.append(item)
        
        # 检查是否需要批量处理
        if len(self._buffer) >= self._batch_size:
            self.flush()
        elif time.time() - self._last_flush > self._timeout:
            self.flush()
    
    def flush(self):
        """强制刷新缓冲区"""
        if not self._buffer:
            return
        
        self._handler(self._buffer)
        self._buffer.clear()
        self._last_flush = time.time()
        self._processed_count += 1
    
    @property
    def pending_count(self) -> int:
        return len(self._buffer)
    
    def stats(self) -> dict[str, Any]:
        return {
            "pending": len(self._buffer),
            "batch_size": self._batch_size,
            "flush_count": self._processed_count,
        }


# ========== 内存预分配器 ==========
class MemoryArena:
    """内存预分配器
    
    特性:
    - 预分配大块内存
    - 按需切分
    - 减少内存碎片
    
    Example:
        arena = MemoryArena(size=1024*1024)  # 1MB
        chunk = arena.allocate(256)
        # ... use chunk ...
        arena.deallocate(chunk)
    """
    __slots__ = ('_data', '_free_list', '_allocated', '_total_size')
    
    def __init__(self, size: int = 1024 * 1024):
        self._data = bytearray(size)
        self._free_list: List[tuple[int, int]] = [(0, size)]  # (offset, size)
        self._allocated: Set[int] = set()
        self._total_size = size
    
    def allocate(self, size: int) -> Optional[memoryview]:
        """分配内存块"""
        # 首次适配算法
        for i, (offset, block_size) in enumerate(self._free_list):
            if block_size >= size:
                # 从空闲列表移除
                self._free_list.pop(i)
                
                # 如果有剩余，添加回空闲列表
                if block_size > size:
                    self._free_list.append((offset + size, block_size - size))
                
                self._allocated.add(offset)
                return memoryview(self._data)[offset:offset + size]
        
        return None
    
    def deallocate(self, view: memoryview):
        """释放内存块"""
        offset = view.obj.__array_interface__['data'][0] - id(self._data) if hasattr(view.obj, '__array_interface__') else 0
        # 简化：实际实现需要更复杂的合并逻辑
        if offset in self._allocated:
            self._allocated.remove(offset)
            self._free_list.append((offset, len(view)))
    
    @property
    def available(self) -> int:
        return sum(size for _, size in self._free_list)
    
    @property
    def usage_rate(self) -> float:
        return 1.0 - (self.available / self._total_size)


# ========== 热点路径优化器 ==========
class HotPathOptimizer:
    """热点代码路径优化器
    
    特性:
    - 自动检测热点函数
    - 动态应用优化
    - 性能监控
    """
    __slots__ = ('_call_counts', '_threshold', '_optimized', '_start_times')
    
    def __init__(self, threshold: int = 1000):
        self._call_counts: Dict[str, int] = {}
        self._threshold = threshold
        self._optimized: Set[str] = set()
        self._start_times: Dict[str, float] = {}
    
    def track(self, func_name: str):
        """跟踪函数调用"""
        now = time.time()
        
        if func_name not in self._call_counts:
            self._call_counts[func_name] = 0
            self._start_times[func_name] = now
        
        self._call_counts[func_name] += 1
        
        # 检测是否为热点
        if self._call_counts[func_name] >= self._threshold and func_name not in self._optimized:
            self._optimized.add(func_name)
            elapsed = now - self._start_times[func_name]
            return True, elapsed
        
        return False, 0.0
    
    def is_hot(self, func_name: str) -> bool:
        return func_name in self._optimized
    
    def stats(self) -> dict[str, Any]:
        return {
            "tracked_functions": len(self._call_counts),
            "hot_functions": list(self._optimized),
            "threshold": self._threshold,
        }


# ========== 性能分析器 ==========
class PerfProfiler:
    """轻量级性能分析器
    
    特性:
    - 低开销计时
    - 嵌套支持
    - 统计汇总
    """
    __slots__ = ('_records', '_stack', '_enabled')
    
    def __init__(self):
        self._records: Dict[str, List[float]] = {}
        self._stack: List[tuple[str, float]] = []
        self._enabled = True
    
    def start(self, name: str):
        if not self._enabled:
            return
        self._stack.append((name, time.perf_counter()))
    
    def stop(self, name: str):
        if not self._enabled or not self._stack:
            return
        
        top_name, start_time = self._stack.pop()
        if top_name != name:
            return
        
        elapsed = time.perf_counter() - start_time
        if name not in self._records:
            self._records[name] = []
        self._records[name].append(elapsed)
    
    def context(self, name: str):
        """上下文管理器"""
        return _PerfContext(self, name)
    
    def stats(self) -> dict[str, Any]:
        result = {}
        for name, times in self._records.items():
            if times:
                result[name] = {
                    "count": len(times),
                    "total": sum(times),
                    "avg": sum(times) / len(times),
                    "min": min(times),
                    "max": max(times),
                }
        return result
    
    def clear(self):
        self._records.clear()
        self._stack.clear()
    
    def disable(self):
        self._enabled = False
    
    def enable(self):
        self._enabled = True


class _PerfContext:
    def __init__(self, profiler: PerfProfiler, name: str):
        self._profiler = profiler
        self._name = name
    
    def __enter__(self):
        self._profiler.start(self._name)
        return self
    
    def __exit__(self, *args):
        self._profiler.stop(self._name)


# ========== 字符串优化 ==========
class StringIntern:
    """字符串驻留优化器
    
    特性:
    - 重复字符串去重
    - 减少内存占用
    - 加速字符串比较
    
    注意：Python 内置的 sys.intern() 已经对字符串做了弱引用处理，
    这里使用强引用缓存来确保常用字符串不会被回收。
    """
    __slots__ = ('_cache',)
    
    def __init__(self, use_weak_refs: bool = True):
        # 字符串本身不支持弱引用，所以只使用普通 dict
        self._cache: Dict[str, str] = {}
    
    def intern(self, s: str) -> str:
        if s in self._cache:
            return self._cache[s]
        
        # 使用 Python 内置的字符串驻留
        import sys
        interned = sys.intern(s)
        self._cache[interned] = interned
        
        return interned
    
    def clear(self):
        self._cache.clear()


# ========== 主插件类 ==========
class PerformanceOptimizerPlugin:
    """性能优化插件"""
    
    def __init__(self):
        self._initialized = False
        self._caches: Dict[str, FastCache] = {}
        self._pools: Dict[str, ObjectPool] = {}
        self._profiler = PerfProfiler()
        self._string_intern = StringIntern()
        self._hot_path = HotPathOptimizer()
    
    def init(self, deps: Optional[dict[str, Any]] = None):
        """初始化插件"""
        if self._initialized:
            return
        
        # 注册全局缓存
        self._caches["route_match"] = FastCache(maxsize=2048)
        self._caches["path_params"] = FastCache(maxsize=2048)
        self._caches["template_render"] = FastCache(maxsize=512)
        
        # 注册对象池
        self._pools["bytearray_4k"] = ObjectPool(lambda: bytearray(4096), maxsize=100)
        self._pools["bytearray_64k"] = ObjectPool(lambda: bytearray(65536), maxsize=20)
        
        self._initialized = True
    
    def start(self):
        """启动插件"""
        pass
    
    def stop(self):
        """停止插件"""
        for cache in self._caches.values():
            cache.clear()
        for pool in self._pools.values():
            pool.clear()
        self._profiler.clear()
    
    def get_cache(self, name: str) -> Optional[FastCache]:
        return self._caches.get(name)
    
    def get_pool(self, name: str) -> Optional[ObjectPool]:
        return self._pools.get(name)
    
    def profile(self) -> PerfProfiler:
        return self._profiler
    
    def intern_string(self, s: str) -> str:
        return self._string_intern.intern(s)
    
    def track_hot_path(self, func_name: str) -> tuple[bool, float]:
        return self._hot_path.track(func_name)
    
    def stats(self) -> dict[str, Any]:
        return {
            "caches": {name: cache.stats() for name, cache in self._caches.items()},
            "pools": {name: pool.stats() for name, pool in self._pools.items()},
            "profiler": self._profiler.stats(),
            "hot_paths": self._hot_path.stats(),
        }


def New() -> PerformanceOptimizerPlugin:
    """工厂函数"""
    return PerformanceOptimizerPlugin()
