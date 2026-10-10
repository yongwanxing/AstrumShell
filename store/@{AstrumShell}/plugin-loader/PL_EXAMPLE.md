# PL 注入机制使用说明

## 概述

PL 注入机制允许插件通过 `PL/` 文件夹向插件加载器注册自定义功能。插件加载器在启动时会自动扫描所有插件，检查其 `manifest.json` 中是否声明了 `pl_injection` 配置项。

## 使用步骤

### 1. 在 manifest.json 中声明 pl_injection

在插件的 `manifest.json` 的 `config.args` 中添加 `"pl_injection": true`：

```json
{
  "metadata": {
    "name": "my-plugin",
    "version": "1.0.0",
    "author": "MyName",
    "description": "我的插件",
    "type": "utility"
  },
  "config": {
    "enabled": true,
    "args": {
      "pl_injection": true
    }
  },
  "dependencies": [],
  "permissions": []
}
```

### 2. 创建 PL/ 文件夹和 PL/main.py

在插件目录下创建 `PL/` 文件夹，并在其中创建 `main.py`：

```
store/@{MyName}/my-plugin/
├── manifest.json      # 声明 pl_injection: true
├── main.py            # 插件主逻辑
├── PL/                # PL 注入文件夹
│   └── main.py        # 注入逻辑（必须包含 register() 函数）
└── README.md
```

### 3. 实现 PL/main.py

`PL/main.py` 必须导出一个 `register(injector)` 函数，接收一个 `PLInjector` 实例：

```python
# PL/main.py
"""PL 注入 - 向插件加载器注册功能"""

def register(injector):
    """向插件加载器注册功能
    
    Args:
        injector: PLInjector 实例，提供以下注册方法：
            - register_function(name, func, description="")
            - register_route(method, path, handler)
            - register_event_handler(event_name, handler)
    """
    
    # 示例 1: 注册一个普通功能
    def my_helper():
        print("这是从 PL 注入的功能")
    
    injector.register_function("my_helper", my_helper, "一个辅助功能")
    
    # 示例 2: 注册 HTTP 路由
    def hello_handler(request):
        return {"message": "Hello from PL injection!"}
    
    injector.register_route("GET", "/pl/hello", hello_handler)
    
    # 示例 3: 注册事件处理器
    def on_plugin_started(plugin_name):
        print(f"插件 {plugin_name} 已启动")
    
    injector.register_event_handler("plugin.started", on_plugin_started)
```

### 4. 引用其他文件

`PL/main.py` 可以引用 `PL/` 文件夹下的其他 Python 文件：

```
store/@{MyName}/my-plugin/PL/
├── main.py            # 入口，包含 register() 函数
├── helpers.py         # 辅助函数（被 main.py 引用）
└── routes.py          # 路由定义（被 main.py 引用）
```

```python
# PL/main.py
from .helpers import format_response
from .routes import register_routes

def register(injector):
    def my_handler():
        return format_response("Hello")
    injector.register_function("my_handler", my_handler)
    register_routes(injector)
```

## 行为说明

| 场景 | 结果 |
|------|------|
| manifest.json 中 `pl_injection: true` + 存在 `PL/main.py` | ✅ 正常加载，执行注入 |
| manifest.json 中 `pl_injection: true` + 缺少 `PL/` 文件夹 | ❌ 警告并拒绝加载该插件 |
| manifest.json 中 `pl_injection: true` + 存在 `PL/` 但缺少 `main.py` | ❌ 警告并拒绝加载该插件 |
| manifest.json 中未声明 `pl_injection` | ✅ 正常加载，跳过 PL 检查 |
| manifest.json 中 `pl_injection: false` | ✅ 正常加载，跳过 PL 检查 |

## 安全限制

PL 注入机制实施了多层安全限制，防止恶意代码注入：

### 1. 文件类型限制
- PL 文件夹中禁止包含 `.sh`、`.bat`、`.exe`、`.dll`、`.so`、`.dylib`、`.bin` 等可执行/二进制文件
- 违反则拒绝加载该插件

### 2. 静态源码安全检查
PL/main.py 源码在编译前会进行静态扫描，禁止以下操作：
- 导入系统级模块（`os`、`sys`、`subprocess`、`shutil`、`socket`、`ctypes`、`cffi`、`multiprocessing`、`threading`）
- 使用 `__import__`、`exec`、`eval`、`compile`
- 直接操作文件（`open`）
- 访问 `__builtins__`

### 3. 沙箱执行环境
PL/main.py 在受限的沙箱中执行，仅提供安全的 builtins：
- 基础类型：`dict`、`list`、`str`、`int`、`float`、`bool`、`tuple`、`set`
- 安全函数：`len`、`range`、`enumerate`、`zip`、`map`、`filter`、`sorted` 等
- 异常类型：`Exception`、`ValueError`、`TypeError`、`KeyError`、`IndexError`

### 4. 参数校验
| 校验项 | 限制 |
|--------|------|
| 功能名称 | 仅允许字母、数字、下划线、冒号、斜杠、连字符、点，最长 128 字符 |
| 路由路径 | 必须以 `/` 开头，禁止 `..`、`//`、`/\.`、`~`、`%`，最长 256 字符 |
| HTTP 方法 | 仅允许 GET、POST、PUT、DELETE、PATCH、HEAD、OPTIONS |
| 事件名称 | 字母开头，仅允许字母、数字、点、下划线，最长 128 字符 |
| 功能描述 | 最长 256 字符 |

### 5. 数量限制
| 限制项 | 上限 |
|--------|------|
| 每个插件最多注册的功能数 | 50 |
| 每个功能名称最多被注册次数 | 10 |

### 6. 异常安全
- 所有注册的函数会被自动包装，执行时抛出异常不会影响主流程
- 异常会被记录到日志，函数返回 `None`

### 7. 调用者溯源
- 通过栈帧回溯自动识别调用者插件名
- 防止其他插件冒充注册

## 注入器 API

`PLInjector` 实例提供以下方法供 `PL/main.py` 调用：

| 方法 | 说明 |
|------|------|
| `register_function(name, func, description="")` | 注册一个注入功能 |
| `register_route(method, path, handler)` | 注册 HTTP 路由 |
| `register_event_handler(event_name, handler)` | 注册事件处理器 |
| `get_injected_functions(name=None)` | 获取已注册的注入功能 |
| `get_injection_info(plugin_name=None)` | 获取注入信息 |
| `has_injection(plugin_name)` | 检查插件是否有 PL 注入 |
| `get_registry_info()` | 获取注册表完整信息（用于监控） |