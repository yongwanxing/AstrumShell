# 依赖自动安装插件 (auto-dependency)

## 概述

依赖自动安装插件是一个核心系统插件，用于扫描所有插件的声明文件，检查并自动安装系统依赖。

## 功能特性

1. **扫描插件声明** - 自动扫描所有插件目录下的 `manifest.json` 文件
2. **系统依赖检测** - 读取每个插件声明的系统依赖 (`system_dependencies` 字段)
3. **安装状态检查** - 检查这些系统依赖是否已在系统中安装
4. **自动安装** - 对于未安装的依赖，使用系统包管理器自动安装
5. **PL 注入接口** - 通过 PL 注入机制向插件加载器注册功能接口

## 使用方法

### 在 manifest.json 中声明系统依赖

其他插件可以在自己的 `manifest.json` 中声明所需的系统依赖：

```json
{
  "metadata": {
    "name": "my-plugin",
    "version": "1.0.0",
    "author": "MyName",
    "description": "我的插件"
  },
  "config": {
    "enabled": true,
    "args": {}
  },
  "dependencies": ["plugin-loader"],
  "system_dependencies": ["curl", "git", "wget"],
  "permissions": []
}
```

### 通过 PL 注入接口调用

插件加载器加载此插件后，可以通过以下 PL 注入接口进行操作：

| 接口名称 | 说明 | 参数 | 返回值 |
|---------|------|------|--------|
| `auto-dependency:scan` | 扫描所有插件的声明文件 | `scan_dir` (可选，默认 "store") | 插件信息列表 |
| `auto-dependency:check` | 检查系统依赖安装状态 | `scan_dir` (可选，默认 "store") | 检查结果字典 |
| `auto-dependency:install` | 安装缺失的系统依赖 | `scan_dir` (可选，默认 "store") | 安装结果字典 |
| `auto-dependency:info` | 获取插件系统信息 | 无 | 系统信息字典 |

### 示例代码

```python
# 获取插件加载器中的 auto-dependency 功能
injector = get_pl_injector()  # 从插件加载器获取

# 扫描所有插件的系统依赖声明
plugins = injector.get_injected_functions("auto-dependency:scan")[0]()
print(f"找到 {len(plugins)} 个插件")

# 检查依赖安装状态
result = injector.get_injected_functions("auto-dependency:check")[0]()
print(f"已安装：{result['installed_count']}, 缺失：{result['missing_count']}")

# 安装缺失的依赖
install_result = injector.get_injected_functions("auto-dependency:install")[0]()
print(f"成功安装：{install_result['success_count']}, 失败：{install_result['failed_count']}")
```

## 支持的包管理器

插件自动检测系统使用的包管理器，支持：

- **Debian/Ubuntu**: apt-get, apt
- **RHEL/CentOS**: yum, dnf
- **Arch Linux**: pacman
- **macOS**: brew
- **Alpine Linux**: apk

## 配置选项

在 `manifest.json` 的 `config.args` 中可以配置：

```json
{
  "config": {
    "enabled": true,
    "args": {
      "scan_dirs": ["store"],
      "package_manager": "auto",
      "auto_install": true
    }
  }
}
```

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| `scan_dirs` | 要扫描的目录列表 | `["store"]` |
| `package_manager` | 包管理器（auto 为自动检测） | `"auto"` |
| `auto_install` | 是否自动安装缺失的依赖 | `true` |

## 安全说明

- 插件需要 `*` 权限才能执行系统命令安装包
- 包安装操作有超时限制（300 秒）
- 所有安装操作都会记录日志

## 文件结构

```
store/@{AstrumShell}/auto-dependency/
├── manifest.json      # 插件清单
├── main.py            # 主逻辑实现
├── PL/
│   └── main.py        # PL 注入入口
└── README.md          # 本文档
```
