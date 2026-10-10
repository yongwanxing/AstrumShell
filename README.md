# AstrumShell · 星辰壳

> 插件化运行时框架 —— 内核保持最小，能力全部以插件形式装载。

![Version](https://img.shields.io/badge/version-v1.2.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-yellow)
![License](https://img.shields.io/badge/license-Apache--2.0-green)
![Plugins](https://img.shields.io/badge/plugins-23%20runnable-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

---

## 30 秒上手

| 方式 | 命令 | 访问 |
|---|---|---|
| **Windows** | 双击 `start.bat` | http://localhost:8080 |
| **Linux / macOS** | `bash start.sh` | http://localhost:8080 |
| **Docker** | `docker compose up -d` | http://localhost:8080 |
| **手动** | `pip install -r requirements.txt && python main.py serve` | http://localhost:8080 |

首次启动会自动创建虚拟环境、安装依赖、初始化 `data/` 目录；`start.bat` / `start.sh` 还会做 Python 探测、依赖安装与崩溃自动重启。

安装为命令后（`pip install -e .`）可用：`astrum serve` / `astrum info` / `astrum version`。

---

## 它是什么

`oss/` 是内核，只做四件事：**插件发现、加载与依赖注入、生命周期管理、日志**。
HTTP API、Web 控制台、国际化、键值存储、签名校验、系统监控……全部是 `store/` 下的插件。

核心机制：

- **一切皆插件** —— 一个插件 = 一个目录：`main.py` + `manifest.json`（可选 `config.json`、`SIGNATURE`）
- **声明式依赖** —— `manifest.json` 声明插件间依赖（`dependencies`），加载器负责拓扑排序与实例注入
- **系统依赖自动安装** —— 支持 `apt / yum / dnf / pacman / brew / apk / winget / choco / scoop`，缺失时按需安装
- **签名与完整性校验** —— 插件可带 RSA-4096 `SIGNATURE`，`signature-verifier` 在加载时校验来源与完整性
- **热插拔与启停** —— `hot-reload` 支持运行时加载/卸载；目录加 `.disabled` 后缀即禁用（控制台可一键切换）
- **国际化** —— 内置 `zh-CN` / `en-US` / `zh-TW`

---

## 目录结构

```
oss/                内核：CLI / 配置 / 插件加载与管理 / 日志 / WebUI 容器
  plugin/           插件基类、加载器、管理器、类型定义、能力注入
  webui/            Web 控制台外壳（导航 + 页面容器）
  core/             内核自带的少量能力（上下文、成就系统）
store/              插件仓库
  @{AstrumShell}/   官方插件（21 个已实现）
  @{Upstream}/      上游社区插件（2 个）
tools/              签名工具：密钥生成 / 批量签名 / 验签
scripts/            端到端冒烟测试
data/               运行期数据（插件存储、密钥、配置缓存）· 已 gitignore
logs/               日志目录 · 已 gitignore
main.py             兼容入口（等价于 astrum serve）
start.bat / start.sh 一键启动（Windows / Linux·macOS）
oss.config.json     运行配置
```

---

## 插件清单

运行时实测加载 **23 个插件**（`GET /api/status` → `plugins_loaded: true`）。

### 官方插件（`@{AstrumShell}`，21 个）

| 插件 | 版本 | 类型 | 说明 | 依赖 | 签名 |
|---|---|---|---|---|---|
| `plugin-loader` | 1.0.0 | core | 插件加载器：扫描、加载、管理所有插件 | — | ✅ |
| `plugin-loader-pro` | 1.0.0 | enhancer | 加载器增强：熔断、降级、容错、自动修复 | plugin-loader | ✅ |
| `dependency` | 1.0.0 | core | 依赖解析：拓扑排序 + 循环依赖检测 | — | ✅ |
| `auto-dependency` | 1.0.0 | core | 扫描插件声明的系统依赖，检查并按需安装 | plugin-loader | — |
| `lifecycle` | 1.0.0 | core | 生命周期管理：状态转换与钩子 | — | ✅ |
| `hot-reload` | 1.0.0 | utility | 热插拔：运行时加载 / 卸载 / 更新插件 | — | ✅ |
| `plugin-storage` | 1.1.0 | utility | 为插件提供隔离的键值存储服务 | i18n | ✅ |
| `plugin-bridge` | 1.1.0 | core | 事件总线 / 广播 / 桥接 / RPC / 共享存储 | plugin-storage, i18n | ✅ |
| `signature-verifier` | 1.1.0 | core | 插件签名验证：完整性与来源校验 | plugin-storage, i18n | ✅ |
| `http-api` | 1.1.0 | protocol | HTTP API 服务：RESTful 路由 + 中间件 | i18n | ✅ |
| `http-tcp` | 1.1.0 | protocol | 基于 TCP 的 HTTP 服务 | i18n | ✅ |
| `ws-api` | 1.1.0 | protocol | WebSocket 服务：实时双向通信、心跳、鉴权 | i18n | ✅ |
| `i18n` | 1.1.0 | middleware | 国际化：翻译加载、语言切换、HTTP 中间件 | — | ✅ |
| `json-codec` | 1.0.0 | utility | 插件间 JSON 编解码与校验 | — | ✅ |
| `performance-optimizer` | 1.0.0 | — | 缓存、对象池、批量处理、内存预分配 | — | — |
| `webui` | 2.1.0 | webui | Web 控制台：多语言、插件管理、系统监控 | http-api, i18n | ✅ |
| `dashboard` | 1.1.0 | webui-extension | 仪表盘：CPU / 内存 / 磁盘 / 网络实时监控 | http-api, webui, i18n | ✅ |
| `pkg-manager` | 1.1.0 | webui-extension | 插件管理页：列表、启停、卸载、配置、商店 | http-api, webui, plugin-storage, i18n | ✅ |
| `log-terminal` | 1.0.0 | webui-extension | 日志查看器与 SSH 终端 | http-api, webui | ✅ |
| `code-reviewer` | 1.0.0 | tool | 代码审查器：扫描未定义引用等问题 | — | ✅ |
| `nodejs-adapter` | — | — | Node.js 生态适配：插件内执行 npm / node | — | — |

### 上游社区插件（`@{Upstream}`，2 个）

| 插件 | 版本 | 说明 | 签名 |
|---|---|---|---|
| `html-render` | 1.0.0 | HTML 渲染与页面服务 | ✅ |
| `web-toolkit` | 1.0.0 | 静态文件服务、模板渲染、路由工具 | ✅ |

### 仅清单占位（未实现，5 个）

`firewall`、`frp-proxy`、`ftp-server`、`polyglot-deploy`、`example-with-deps` —— 目录里只有 `manifest.json`，尚未实现功能，可作为第三方插件的声明示例。

---

## 使用

### 命令行

```bash
astrum serve                     # 启动服务（默认 0.0.0.0:8080）
astrum serve --port 9000         # 指定端口
astrum serve --tcp-port 9002     # 指定 HTTP-over-TCP 端口
astrum info                      # 显示配置与系统信息
astrum version
python main.py serve             # 未做可编辑安装时的等价用法
```

### 配置 `oss.config.json`

| 键 | 默认值 | 说明 |
|---|---|---|
| `HOST` | `0.0.0.0` | 监听地址 |
| `HTTP_API_PORT` | `8080` | HTTP API + Web 控制台 |
| `HTTP_TCP_PORT` | `8082` | HTTP over TCP 服务 |
| `DATA_DIR` | `./data` | 运行期数据目录 |
| `STORE_DIR` | `./store` | 插件仓库 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `PERMISSION_CHECK` | `true` | 插件权限检查 |
| `MAX_WORKERS` | `4` | 工作线程数 |

WebSocket 端口由 `ws-api` 插件的 `config.args.port` 决定（默认 **8081**）。

### 页面与接口（本地实测均返回 200）

| 路径 | 说明 |
|---|---|
| `/` | 入口页，自动跳转到 `/dashboard` |
| `/dashboard` | 仪表盘：CPU / 内存 / 磁盘 / 网络 |
| `/packages` | 插件管理：列表、启停、卸载 |
| `/store` | 插件商店视图 |
| `/health` | 健康检查（供 Docker healthcheck 使用） |
| `/api/status` | 运行状态、插件加载情况 |
| `/api/plugins` | 已安装插件列表（JSON） |
| `/api/dashboard/stats` · `/api/dashboard/history` | 监控数据与历史曲线 |
| `/api/terminal/sessions` | 终端会话列表 |

> **已知问题**：`/api/i18n/*` 与 `/api/logs/get` 目前返回 404 —— 这两个插件在 `start()` 阶段才注册路由，未挂到服务路由表，待修。

### Docker

```bash
docker compose up -d
```

- 端口：`8080`（API + WebUI）、`8081`（WebSocket）、`8082`（TCP）
- `store/` 以只读方式挂载 → 更新插件无需重建镜像
- `data/` 使用命名卷持久化；内置 healthcheck

---

## 开发一个插件

```
store/@{yourname}/hello/
├── manifest.json
└── main.py
```

**manifest.json**

```json
{
  "metadata": {
    "name": "hello",
    "version": "0.1.0",
    "author": "yourname",
    "description": "示例插件",
    "type": "utility"
  },
  "config": { "enabled": true, "args": {} },
  "dependencies": ["http-api"],
  "permissions": ["lifecycle"]
}
```

**main.py**

```python
from oss.plugin.types import Plugin, Manifest, Metadata, PluginConfig


class HelloPlugin(Plugin):
    def meta(self):
        return Manifest(
            metadata=Metadata(name="hello", version="0.1.0",
                              author="yourname", description="示例插件"),
            config=PluginConfig(enabled=True, args={}),
            dependencies=["http-api"],
        )

    def init(self, deps=None):
        """依赖注入：deps 是 {依赖名: 插件实例}"""
        self.http_api = (deps or {}).get("http-api")

    def start(self):
        if self.http_api:
            self.http_api.router.get("/api/hello", self._hello)

    def stop(self):
        pass

    def _hello(self, request):
        from oss.plugin.types import Response
        return Response(status=200, body='{"hello": "world"}')
```

生命周期：`init(deps)` → `start()` → `stop()`；启用/禁用只需把目录重命名为 `hello.disabled`。

### 给插件签名

```bash
python tools/sign_plugins.py     # 生成 RSA-4096 密钥对并批量签名
python tools/test_signature.py   # 验证签名
```

- 私钥落在 `data/signature-verifier/keys/private/`（已被 `.gitignore` 排除），**不要提交**
- 生成的公钥需要写入 `store/@{AstrumShell}/signature-verifier/main.py` 的信任锚变量
- 仓库内当前信任锚为历史公钥、且无私钥 → **首次使用请重新生成自己的密钥对**

---

## 测试与 CI

```bash
python -m compileall -q oss store tools scripts main.py   # 语法与编码检查
python -m pytest -q oss/tests                             # 单元测试（当前 14 项）
python scripts/smoke_serve.py --port 8099                 # 端到端冒烟：起服务 → 探活 → 关停
```

`.github/workflows/ci.yml`：**ubuntu / windows / macos × Python 3.10 / 3.12 / 3.13** → 可编辑安装 → 编译检查 → 单测 → 冒烟测试。

---

## 跨平台注意事项（实际踩过的坑）

- **`.bat` 必须是 CRLF，且不要出现非 ASCII 字符**：cmd 的 `call :label` / `goto` 按字节偏移跳转，UTF-8 中文注释会让跳转错位，甚至执行到行中间的字符
- **批处理括号块内必须用 `!VAR!`**（延迟展开）：`%VAR%` 在解析阶段就展开，块内会得到空值
- **Python 读写文本显式 `encoding="utf-8"`**：Windows 默认 GBK 会破坏 JSON 中的中文
- **日志里的 emoji 要容错**：Windows 控制台无法编码 `⚠` 等字符，直接 print 会抛 `UnicodeEncodeError` 打断服务
- **`.sh` 必须 LF 换行**：`.gitattributes` 已固定 `*.bat`/`*.cmd` 走 CRLF、`.sh` 走 LF

---

## 已知限制与路线图

- 5 个插件仍是清单占位（`firewall` / `frp-proxy` / `ftp-server` / `polyglot-deploy` / `example-with-deps`）
- 部分插件 API 路由未挂载（`/api/i18n/*`、`/api/logs/get` → 404）
- 签名信任锚需要替换为当前维护者自己的密钥
- Linux 侧尚未实机验证（CI 矩阵已就绪，推送后即可获得结果）
- 插件隔离目前是同进程内的权限检查，进程级隔离尚未实现

---

## 许可

[Apache License 2.0](LICENSE)

版本：**v1.2.0**

