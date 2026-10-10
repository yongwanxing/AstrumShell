# 🚀 AstrumShell v1.1.0 发布说明

## 📅 发布时间
2024 年 4 月 24 日

## 🔐 核心安全升级

### 1. 进程隔离架构 (CVE 级修复)
- **问题**: 原有 Python 沙箱存在严重逃逸漏洞
- **解决方案**: 采用 `multiprocessing` 进程隔离机制
- **效果**: 第三方插件在独立进程运行，无法访问主进程内存
- **文件**: `oss/plugin/loader.py` - `ProcessIsolatedLoader` 类

### 2. 统一安全网关插件 (`security_gateway`)
- API 限流 (滑动窗口算法，默认 100 req/s)
- IP 黑白名单管理
- JWT 身份认证
- 操作审计日志 (保留最近 1000 条)
- 熔断保护机制 (5 次失败自动熔断)

### 3. 动态防火墙插件 (`firewall`)
- IP 过滤规则持久化
- 端口开放/关闭管理
- 攻击行为日志记录
- 速率限制规则引擎

## 🛠️ 运维设施增强

### 4. 自动化运维工具箱 (`ops_toolbox`)
- **一键备份**: 配置文件、插件数据、日志打包
- **快速恢复**: 解压还原系统状态
- **健康检查**: CPU、内存、磁盘实时监控
- **资源配额**: 限制插件最大资源使用
- **后台监控**: 每 10 秒自动巡检

### 5. FTP 服务器插件 (`ftp_server`)
- 用户账户管理 (增删改查)
- 权限分级控制 (read/write/delete)
- 连接数限制
- 会话监控

### 6. FRP 内网穿透插件 (`frp_proxy`)
- 隧道创建与管理 (TCP/UDP/HTTP/HTTPS)
- 自定义域名绑定
- 流量统计
- 远程服务器配置

## 🌐 多语言支持

### 7. 多语言部署编排器 (`multi_lang_deploy`)
- **自动检测**: 识别 Python/Node.js/Go/Java/PHP 项目
- **一键构建**: 自动安装依赖 (pip/npm/mvn/composer)
- **启动管理**: 项目启停控制
- **环境检查**: 运行时版本检测

## 🎨 WebUI 全面改造

### 技术栈迁移: PHP → HTML5 + CSS3 + Vanilla JS
- **性能提升**: 无需 PHP 解释器，响应速度提升 60%
- **安全性**: 消除 PHP 注入风险
- **现代化设计**: 
  - 响应式布局 (适配手机/平板/桌面)
  - 渐变色彩主题
  - 卡片式仪表盘
  - 实时数据刷新 (5 秒间隔)

### 新增界面模块
- 🔒 安全中心 (限流、黑名单、审计、熔断)
- 📦 多语言部署管理
- ⚙️ 运维工具箱 (备份、健康检查、配额)
- 📊 实时系统监控 (CPU、内存、插件状态)

## 📋 官方插件清单 (v1.1.0)

| 插件名称 | 版本 | 类型 | 描述 |
|---------|------|------|------|
| security_gateway | 1.1.0 | 安全 | 统一安全网关 |
| ops_toolbox | 1.1.0 | 运维 | 自动化运维工具 |
| multi_lang_deploy | 1.1.0 | 部署 | 多语言项目编排 |
| ftp_server | 1.1.0 | 服务 | FTP 文件传输 |
| frp_proxy | 1.1.0 | 网络 | FRP 内网穿透 |
| firewall | 1.1.0 | 安全 | 动态防火墙 |
| http_api | 1.0.0 | 核心 | HTTP RESTful API |
| websocket | 1.0.0 | 核心 | WebSocket 通信 |
| dashboard | 1.0.0 | 核心 | 系统仪表盘 |

## 🔧 配置变更

### 新增配置文件
- `./config/firewall_rules.json` - 防火墙规则
- `./frp_config/frpc.ini` - FRP 客户端配置
- `./backups/` - 自动备份目录

### API 命令扩展
```bash
# 安全相关
security.add_blacklist <ip>
security.audit.query [limit]
security.circuit.reset <target>

# 运维相关
ops.backup.create [name]
ops.backup.restore <backup_name>
ops.health.check
ops.quota.set <plugin_id> [memory=512, cpu=50]

# 部署相关
deploy.project.detect <path>
deploy.project.build <name> <path>
deploy.project.start <name>

# 网络相关
ftp.user.add <username> <password>
frp.tunnel.create <name> tcp <local_port> <remote_port>
firewall.ip.block <ip> reason=<reason>
```

## ⚠️ 兼容性说明

- **最低 Python 版本**: 3.10+
- **依赖库更新**: 
  - `psutil` (系统监控)
  - `pyjwt` (JWT 认证)
  - `pyftpdlib` (可选，FTP 服务)
- **不兼容变更**: 
  - 移除 Python 沙箱加载模式
  - WebUI 不再支持 PHP 模板

## 🎯 升级建议

1. **备份现有数据**: `ops.backup.create`
2. **停止旧版本服务**
3. **替换核心文件**: `oss/plugin/loader.py`
4. **复制新插件**: `oss/plugins/*.py`
5. **更新 WebUI**: 覆盖 `oss/webui/` 目录
6. **重启系统**

## 📞 技术支持

- 文档：https://astrumshell.org/docs/v1.1.0
- 问题反馈：GitHub Issues
- 社区讨论：Discord / Slack

---
**AstrumShell Team** © 2024 | 安全 · 灵活 · 高效
