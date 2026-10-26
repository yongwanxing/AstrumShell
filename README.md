# AstrumShell · 星辰壳

> 插件化运行时框架 —— 内核保持最小，能力全部以插件形式装载。

![Version](https://img.shields.io/badge/version-v1.2.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-yellow)
![License](https://img.shields.io/badge/license-Apache--2.0-green)
![Plugins](https://img.shields.io/badge/plugins-23%20runnable-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

---

## 它是什么

`oss/` 是内核，只做四件事：**插件发现、加载与依赖注入、生命周期管理、日志**。
HTTP API、Web 控制台、国际化、键值存储、签名校验、系统监控……全部是 `store/` 下的插件。

核心机制：

- **一切皆插件** —— 一个插件 = 一个目录：`main.py` + `manifest.json`（可选 `config.json`、`SIGNATURE`）
- **声明式依赖** —— `manifest.json` 声明插件间依赖（`dependencies`），加载器负责拓扑排序与实例注入
- **系统依赖自动安装** —— 支持 `apt / yum / dnf / pacman / brew / apk / winget / choco / scoop`，缺失时按需安装
- **签名与完整性校验** —— 插件可带 RSA-4096 `SIGNATURE`；加载器**在导入插件代码之前**校验，强制模式下签名不通过直接拒绝加载（自举阶段除外）
- **热插拔与启停** —— `hot-reload` 支持运行时加载/卸载；目录加 `.disabled` 后缀即禁用（控制台可一键切换）
- **控制台** —— WebUI 容器 + 设置页：主题切换、语言切换、仪表盘刷新间隔都持久化（存 `data/webui/`），仪表盘走前端轮询实时更新
- **国际化** —— 内置 `zh-CN` / `en-US` / `zh-TW`

---

## 下载与部署

### 方式一：Git 克隆（推荐）

```bash
git clone https://github.com/yongwanxing/AstrumShell.git
cd AstrumShell
```

克隆后直接按 [快速上手](#快速上手) 启动即可，无需编译、无需构建。

### 方式二：直接下载源码包（不用 Git）

| 格式 | 地址 |
|---|---|
| ZIP | `https://github.com/yongwanxing/AstrumShell/archive/refs/heads/main.zip` |
| tar.gz | `https://github.com/yongwanxing/AstrumShell/archive/refs/heads/main.tar.gz` |

下载后解压 → 进入目录 → 按「快速上手」运行。（网络访问 GitHub 不畅时，请自行准备代理或使用镜像）

### 方式三：Docker

```bash
# A. compose（推荐：自带只读插件挂载 + 健康检查）
docker compose up -d
docker compose logs -f        # 查看启动日志
docker compose down           # 停止

# B. 手动构建与运行
docker build -t astrumshell .
docker run -d --name astrumshell \
  -p 8080:8080 -p 8081:8081 -p 8082:8082 \
  -v astrumshell-data:/app/data \
  astrumshell
```

- 端口：`8080` HTTP API + Web 控制台 · `8081` WebSocket · `8082` HTTP over TCP
- `store/` 以**只读**方式挂载 → 更新插件无需重建镜像
- `data/`（插件存储 / 密钥 / 日志）落在命名卷 `astrumshell-data`
- 镜像内置健康检查（打 `/health`），`restart: unless-stopped` 自动拉起

### 方式四：pip 安装（作为依赖库或本地开发）

```bash
pip install -r requirements.txt
pip install -e .        # 安装后可用 astrum 命令
```

### 环境要求

| 项 | 要求 |
|---|---|
| Python | **≥ 3.10**（CI 覆盖 3.10 / 3.12 / 3.13，本地实测 3.14） |
| 操作系统 | Windows 10+ / Linux / macOS（CI 三平台全绿） |
| 可选依赖 | Node.js（`nodejs-adapter` 插件需要）、Docker（容器部署） |
| 端口 | 默认需要 `8080` / `8081` / `8082` 可用 |

### 部署后自检

```bash
curl http://localhost:8080/health        # 期望 HTTP 200
curl http://localhost:8080/api/status    # 期望 {"status": "running", "plugins_loaded": true}
```

浏览器打开 <http://localhost:8080> → 自动跳转到 `/dashboard` 仪表盘；`/packages` 是插件管理页。

---

## 快速上手  

| 方式 | 命令 | 访问 |
|---|---|---|
| **Windows** | 双击 `start.bat` | http://localhost:8080 |
| **Linux / macOS** | `bash start.sh` | http://localhost:8080 |
| **Docker** | `docker compose up -d` | http://localhost:8080 |
| **手动** | `pip install -r requirements.txt && python main.py serve` | http://localhost:8080 |

首次启动会自动创建虚拟环境、安装依赖、初始化 `data/` 目录；`start.bat` / `start.sh` 还会做 Python 探测、依赖安装与崩溃自动重启。

安装为命令后（`pip install -e .`）可用：`astrum serve` / `astrum info` / `astrum version`。

---

## 目录结构

```
oss/                内核：CLI / 配置 / 插件加载与管理 / 日志 / WebUI 容器
  plugin/           插件基类、加载器、管理器、类型定义、能力注入
                    content_hash.py 插件内容哈希（跨平台一致）
                    runtime.py 插件运行时定位（依赖成环时按名字取实例）
                    translate.py 翻译辅助（i18n 不可用自动回退）
  webui/            Web 控制台外壳（导航 + 页面容器）
  core/             内核自带的少量能力（上下文、成就系统）
  console.py        跨平台控制台（stdout 编码策略）
store/              插件仓库
  @{AstrumShell}/   官方插件（21 个已实现；webui 提供 /settings 设置页，dashboard 提供实时仪表盘）
  @{Upstream}/      上游社区插件（2 个）
tools/              签名工具：批量签名 / 信任锚同步 / 验签
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
| `auto-dependency` | 1.0.0 | core | 扫描插件声明的系统依赖，检查并按需安装 | plugin-loader | ✅ |
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
| `performance-optimizer` | 1.0.0 | — | 缓存、对象池、批量处理、内存预分配 | — | ✅ |
| `webui` | 2.1.0 | webui | Web 控制台：多语言、插件管理、系统监控 | http-api, i18n | ✅ |
| `dashboard` | 1.1.0 | webui-extension | 仪表盘：CPU / 内存 / 磁盘 / 网络实时监控 | http-api, webui, i18n | ✅ |
| `pkg-manager` | 1.1.0 | webui-extension | 插件管理页：列表、启停、卸载、配置、商店 | http-api, webui, plugin-storage, i18n | ✅ |
| `log-terminal` | 1.0.0 | webui-extension | 日志查看器与 SSH 终端 | http-api, webui | ✅ |
| `code-reviewer` | 1.0.0 | tool | 代码审查器：扫描未定义引用等问题 | — | ✅ |
| `nodejs-adapter` | — | — | Node.js 生态适配：插件内执行 npm / node | — | ✅ |

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
| `/dashboard` | 系统仪表盘：CPU / 内存 / 磁盘表盘 + 网络 / IO / 延迟实时曲线（前端轮询，不整页刷新） |
| `/settings` | 系统设置：主题（浅色/深色）、语言、仪表盘刷新间隔 + 只读的系统与安全信息（齿轮图标进入） |
| `/packages` | 插件管理：列表、启停、卸载 |
| `/store` | 插件商店视图 |
| `/health` | 健康检查（供 Docker healthcheck 使用） |
| `/api/status` | 运行状态、插件加载情况 |
| `/api/plugins` | 已安装插件列表（JSON） |
| `/api/settings` | `GET` 读取设置 / `POST` 保存（非法值返回 400），`POST /api/settings/reset` 恢复默认 |
| `/api/dashboard/stats` · `/api/dashboard/history` | 实时指标（后台线程每 2 秒采样）与历史曲线 |
| `/api/i18n/locales` · `/api/i18n/translate?key=…` · `POST /api/i18n/locale` | 语言列表 / 翻译 / 切换语言 |
| `/api/logs/get` | 日志读取 |
| `/api/terminal/sessions` | 终端会话列表 |

> 带查询串的 GET（如 `/api/i18n/translate?key=x`）也能正确命中路由：路由器先剥离 `?query` 再匹配，处理器可从 `request.query` 取值。

### Docker

部署步骤见上方 [下载与部署](#下载与部署) 的**方式三**：容器内端口为 `8080` / `8081` / `8082`，`store/` 只读挂载、`data/` 走命名卷持久化、内置 `/health` 健康检查。

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
python tools/sign_plugins.py                    # 复用/生成密钥 → 同步信任锚 → 为所有官方插件签名
python tools/update_trust_anchors.py --check    # 校验信任锚与本地密钥是否一致
python tools/test_signature.py                  # 逐个插件验签 + 篡改检测
```

信任链约定：

- **私钥**在 `data/signature-verifier/keys/private/`（`.gitignore` 已排除）→ 请离线备份，**丢失后无法再签出合法签名**
- **公钥（信任锚）**内嵌在 `store/@{AstrumShell}/signature-verifier/main.py`，由 `tools/update_trust_anchors.py` 自动写入，不要手工复制
- 轮换密钥：`python tools/sign_plugins.py --new-keys` → 作废所有现有签名，脚本会自动同步信任锚并重新签名（默认不加 `--new-keys` 时**复用**已有私钥，避免误轮换）
- **加载时强制校验**：`ENFORCE_SIGNATURE=true`（默认）→ 验签失败的插件被拒绝加载并打印原因；设为 `false` 只告警、仍加载
- **自举豁免**：`plugin-loader` 自身与 `signature-verifier` 自身在验签服务就绪前加载，不参与强制校验
- **哈希与平台无关**：文本文件按 LF 归一化、相对路径统一 `/`、跳过 `__pycache__`，因此同一插件在 Windows / Linux / macOS 上验签结果一致（见 `oss/plugin/content_hash.py`）

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
- **命令行脚本要防 stdout 编码崩溃**：Windows 下输出被重定向（管道 / CI 捕获）时 Python 用本地编码（GBK），打印 `✓ ⚠ ✗` 会抛 `UnicodeEncodeError` 直接中断脚本；脚本入口先调用 `oss.console.setup_console()`（控制台保留系统编码，重定向统一 UTF-8 + 降级替换）
- **签名哈希必须与平台无关**：插件目录哈希若直接吃原始字节 + `str(相对路径)`，会在 CRLF/LF、`\`/`/` 之间算出不同结果，导致跨平台验签失败；统一走 `oss/plugin/content_hash.py`
- **`Path.write_text` 的换行**：默认会把 `\n` 转成 CRLF，写 `SIGNATURE` 这类需要跨平台字节一致的文本必须显式 `newline="\n"`（Python 3.10+ 支持）

---

## 已知限制与路线图

- 5 个插件仍是清单占位（`firewall` / `frp-proxy` / `ftp-server` / `polyglot-deploy` / `example-with-deps`）
- 控制台图标字体走 CDN（remixicon）：离线环境下图标不显示，功能与文案不受影响
- i18n 中间件尚未挂进 http-api 的中间件链，因此界面语言取自**设置**而不是请求头 `Accept-Language`
- 设置页的语言切换覆盖设置页与仪表盘；其他插件自带的页面文案由各插件提供
- 插件隔离目前是同进程内的权限检查，进程级隔离尚未实现
- 签名信任锚已与仓库内 `tools/sign_plugins.py` 的密钥同步；**私钥不在仓库**（`data/signature-verifier/keys/private/`），需离线备份，丢失后只能用 `--new-keys` 轮换信任锚并重签全部插件

---

## 许可

[Apache License 2.0](LICENSE)

版本：**v1.2.0**

