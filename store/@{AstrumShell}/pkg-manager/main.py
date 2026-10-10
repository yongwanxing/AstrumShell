"""包管理插件 - 提供插件配置管理和商店界面"""
import os
import sys
import json
import html
import urllib.request
from pathlib import Path
from oss.logger.logger import Log
from oss.plugin.types import Plugin, Response, register_plugin_type


# Gitee 仓库配置
GITEE_OWNER = "yongwanxing"
GITEE_REPO = "astrum-shell"
GITEE_BRANCH = "main"
# 使用 raw 文件 URL（不走 API，无频率限制）
GITEE_RAW_BASE = f"https://gitee.com/{GITEE_OWNER}/{GITEE_REPO}/raw/{GITEE_BRANCH}"
GITEE_API_BASE = f"https://gitee.com/api/v5/repos/{GITEE_OWNER}/{GITEE_REPO}/contents"
# Gitee Token（从环境变量读取，可选）
GITEE_TOKEN = os.environ.get("GITEE_TOKEN", "")


def _gitee_request(url: str, timeout: int = 15):
    """Gitee 请求"""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "AstrumShell-PkgManager")
    if GITEE_TOKEN:
        # Gitee 使用私人令牌认证
        req.add_header("Authorization", f"token {GITEE_TOKEN}")
    return urllib.request.urlopen(req, timeout=timeout)


class PkgManagerPlugin(Plugin):
    """包管理插件"""

    def __init__(self):
        self.webui = None
        self.storage = None
        self.store_dir = Path("./store")
        self._remote_cache = None
        self._cache_time = 0
        self._cache_ttl = 300  # 5分钟缓存

    def meta(self):
        from oss.plugin.types import Metadata, PluginConfig, Manifest
        return Manifest(
            metadata=Metadata(
                name="pkg-manager",
                version="1.0.0",
                author="AstrumShell",
                description="插件包管理器 - 配置管理和商店"
            ),
            config=PluginConfig(enabled=True, args={}),
            dependencies=["http-api", "webui", "plugin-storage"]
        )

    def set_webui(self, webui):
        self.webui = webui

    def set_plugin_storage(self, storage):
        self.storage = storage

    def init(self, deps: dict = None):
        """init 阶段：注册页面到 WebUI"""
        if not self.webui:
            Log.warn("pkg-manager", "警告: 未找到 WebUI 依赖")
            return

        self.webui.register_page(
            path='/packages',
            content_provider=self._packages_content,
            nav_item={'icon': 'ri-apps-line', 'text': '插件管理'}
        )
        self.webui.register_page(
            path='/store',
            content_provider=self._store_content,
            nav_item={'icon': 'ri-store-2-line', 'text': '插件商店'}
        )
        Log.info("pkg-manager", "已注册到 WebUI 导航")

    def start(self):
        """启动阶段：注册 API 路由"""
        if not self.webui or not hasattr(self.webui, 'server') or not self.webui.server:
            Log.warn("pkg-manager", "警告: WebUI 服务器未就绪")
            return

        router = self.webui.server.router

        # API - 已安装插件
        router.get("/api/plugins", self._handle_list_plugins)
        router.get("/api/plugins/:name/config", self._handle_get_config)
        router.post("/api/plugins/:name/config", self._handle_save_config)
        router.get("/api/plugins/:name/info", self._handle_get_plugin_info)
        router.post("/api/plugins/:name/uninstall", self._handle_uninstall)

        # API - 页面按钮调用（请求体传参，与前端 /api/plugins/toggle|uninstall|install 对齐）
        router.post("/api/plugins/toggle", self._handle_toggle)
        router.post("/api/plugins/uninstall", self._handle_uninstall)
        router.post("/api/plugins/install", self._handle_store_install)

        # API - 远程商店
        router.get("/api/store/remote", self._handle_remote_store)
        router.post("/api/store/install", self._handle_store_install)

        Log.info("pkg-manager", "包管理器已启动")

    def stop(self):
        Log.error("pkg-manager", "包管理器已停止")

    # ==================== 页面渲染 ====================

    def _packages_content(self) -> str:
        """渲染插件管理页面 - 纯 HTML/Python 模板"""
        try:
            # 获取已安装的插件列表
            plugins = self._get_installed_plugins()
            plugin_rows = ""
            for pkg_name, info in plugins.items():
                status_class = "success" if info.get('enabled', False) else "secondary"
                status_text = "已启用" if info.get('enabled', False) else "已禁用"
                # XSS 防护：对所有用户数据进行 HTML 转义
                safe_pkg_name = html.escape(pkg_name)
                safe_version = html.escape(str(info.get('version', '未知')))
                safe_author = html.escape(str(info.get('author', '未知')))
                plugin_rows += f"""
                <tr>
                    <td>{safe_pkg_name}</td>
                    <td>{safe_version}</td>
                    <td>{safe_author}</td>
                    <td><span class="badge badge-{status_class}">{status_text}</span></td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="togglePlugin('{safe_pkg_name}')">切换状态</button>
                        <button class="btn btn-sm btn-danger" onclick="uninstallPlugin('{safe_pkg_name}')">卸载</button>
                    </td>
                </tr>"""
            
            page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>插件管理</title>
    <link rel="stylesheet" href="/assets/remixicon.css">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f6fa; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 20px; }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
        .card-title {{ font-size: 18px; font-weight: 600; color: #2c3e50; }}
        .btn {{ padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; transition: all 0.3s; }}
        .btn-primary {{ background: #3498db; color: white; }}
        .btn-primary:hover {{ background: #2980b9; }}
        .btn-danger {{ background: #e74c3c; color: white; }}
        .btn-danger:hover {{ background: #c0392b; }}
        .btn-sm {{ padding: 4px 8px; font-size: 12px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ecf0f1; }}
        th {{ background: #f8f9fa; font-weight: 600; color: #2c3e50; }}
        tr:hover {{ background: #f8f9fa; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
        .badge-success {{ background: #d5f5e3; color: #27ae60; }}
        .badge-secondary {{ background: #e5e7eb; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="card-header">
                <h2 class="card-title"><i class="ri-plug-line"></i> 插件管理</h2>
                <button class="btn btn-primary" onclick="location.href='/store'"><i class="ri-store-line"></i> 前往商店</button>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>插件名称</th>
                        <th>版本</th>
                        <th>作者</th>
                        <th>状态</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    {plugin_rows}
                </tbody>
            </table>
        </div>
    </div>
    <script>
        function togglePlugin(name) {{
            fetch('/api/plugins/toggle', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{plugin: name}})
            }}).then(() => location.reload());
        }}
        function uninstallPlugin(name) {{
            if (confirm('确定要卸载 ' + name + ' 吗？')) {{
                fetch('/api/plugins/uninstall', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{plugin: name}})
                }}).then(() => location.reload());
            }}
        }}
    </script>
</body>
</html>"""
            return page
        except Exception as e:
            return f"<p>插件管理页面渲染出错：{e}</p>"

    def _store_content(self) -> str:
        """渲染插件商店页面 - 纯 HTML/Python 模板"""
        try:
            # 获取可用插件列表
            available = self._get_available_plugins()
            installed = self._get_installed_plugins()
            plugin_cards = ""
            for pkg_name, info in available.items():
                is_installed = pkg_name in installed
                # XSS 防护：对所有用户数据进行 HTML 转义
                safe_pkg_name = html.escape(pkg_name)
                safe_name = html.escape(str(info.get('name', pkg_name)))
                safe_desc = html.escape(str(info.get('description', '暂无描述')))
                safe_version = html.escape(str(info.get('version', '未知')))
                safe_author = html.escape(str(info.get('author', '未知')))
                # JavaScript 中的字符串也需要转义
                js_safe_pkg_name = pkg_name.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')
                action_btn = f'<button class="btn btn-success" onclick="installPlugin(\'{js_safe_pkg_name}\')">安装</button>' if not is_installed else '<button class="btn btn-secondary" disabled>已安装</button>'
                plugin_cards += f"""
                <div class="plugin-card">
                    <div class="plugin-icon"><i class="ri-plug-line"></i></div>
                    <h3>{safe_name}</h3>
                    <p class="plugin-desc">{safe_desc}</p>
                    <div class="plugin-meta">
                        <span>版本：{safe_version}</span>
                        <span>作者：{safe_author}</span>
                    </div>
                    <div class="plugin-actions">
                        {action_btn}
                    </div>
                </div>"""
            
            page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>插件商店</title>
    <link rel="stylesheet" href="/assets/remixicon.css">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f6fa; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 20px; }}
        .card-header {{ margin-bottom: 20px; }}
        .card-title {{ font-size: 18px; font-weight: 600; color: #2c3e50; }}
        .btn {{ padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; transition: all 0.3s; }}
        .btn-success {{ background: #27ae60; color: white; }}
        .btn-success:hover {{ background: #229954; }}
        .btn-secondary {{ background: #95a5a6; color: white; cursor: not-allowed; }}
        .plugins-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }}
        .plugin-card {{ background: #f8f9fa; border-radius: 8px; padding: 20px; transition: transform 0.3s; }}
        .plugin-card:hover {{ transform: translateY(-5px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
        .plugin-icon {{ width: 48px; height: 48px; background: #3498db; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-size: 24px; margin-bottom: 15px; }}
        .plugin-card h3 {{ font-size: 16px; color: #2c3e50; margin-bottom: 10px; }}
        .plugin-desc {{ color: #7f8c8d; font-size: 14px; margin-bottom: 15px; line-height: 1.5; }}
        .plugin-meta {{ display: flex; justify-content: space-between; font-size: 12px; color: #95a5a6; margin-bottom: 15px; }}
        .plugin-actions {{ display: flex; gap: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="card-header">
                <h2 class="card-title"><i class="ri-store-line"></i> 插件商店</h2>
            </div>
            <div class="plugins-grid">
                {plugin_cards}
            </div>
        </div>
    </div>
    <script>
        function installPlugin(name) {{
            fetch('/api/plugins/install', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{plugin: name}})
            }}).then(r => r.json()).then(data => {{
                if (data.success) {{
                    alert('安装成功！');
                    location.reload();
                }} else {{
                    alert('安装失败：' + data.error);
                }}
            }});
        }}
    </script>
</body>
</html>"""
            return page
        except Exception as e:
            return f"<p>插件商店页面渲染出错：{e}</p>"


    # ==================== API 处理 ====================

    def _handle_list_plugins(self, request):
        """列出所有已安装插件"""
        plugins = self._scan_all_plugins()
        return Response(status=200, headers={"Content-Type": "application/json"}, body=json.dumps(plugins, ensure_ascii=False))

    def _handle_get_config(self, request):
        """获取插件配置 schema + 当前值"""
        plugin_name = self._resolve_plugin_name(request)
        schema = self._load_config_schema(plugin_name)
        current = self._load_plugin_config(plugin_name)
        return Response(status=200, headers={"Content-Type": "application/json"}, body=json.dumps({
            "schema": schema,
            "current": current
        }, ensure_ascii=False))

    def _handle_save_config(self, request):
        """保存插件配置"""
        try:
            body = self._body_json(request)
            plugin_name = self._resolve_plugin_name(request)
            if not plugin_name:
                return Response(status=400, body='{"error":"缺少插件名"}')
            self._save_plugin_config(plugin_name, body)
            return Response(status=200, headers={"Content-Type": "application/json"}, body='{"ok":true}')
        except Exception as e:
            return Response(status=500, headers={"Content-Type": "application/json"}, body=json.dumps({"error": str(e)}, ensure_ascii=False))

    def _handle_get_plugin_info(self, request):
        """获取插件详细信息"""
        plugin_name = self._resolve_plugin_name(request)
        info = self._get_plugin_detailed_info(plugin_name)
        return Response(status=200, headers={"Content-Type": "application/json"}, body=json.dumps(info, ensure_ascii=False))

    def _handle_uninstall(self, request):
        """卸载插件（同时支持 /api/plugins/:name/uninstall 与 /api/plugins/uninstall）"""
        import shutil
        plugin_name = self._resolve_plugin_name(request)
        if not plugin_name:
            return Response(status=400, body='{"error":"缺少插件名"}')
        # 查找插件目录（包括被禁用、带 .disabled 后缀的）
        plugin_dir = self._find_plugin_dir(plugin_name) or self._find_disabled_plugin_dir(plugin_name)
        if not plugin_dir:
            return Response(status=404, body='{"error":"插件未安装"}')
        try:
            shutil.rmtree(plugin_dir)
            return Response(status=200, headers={"Content-Type": "application/json"},
                            body=json.dumps({"ok": True, "success": True}, ensure_ascii=False))
        except Exception as e:
            return Response(status=500, body=json.dumps({"error": str(e)}, ensure_ascii=False))

    def _handle_toggle(self, request):
        """切换插件启用状态：在 <插件名> 与 <插件名>.disabled 之间重命名目录

        启动时插件加载器会跳过 *.disabled 目录，所以重命名即"禁用/启用"。
        修改在下次启动服务后完全生效（运行中重命名不会卸载已加载的插件）。
        """
        plugin_name = self._resolve_plugin_name(request)
        if not plugin_name:
            return Response(status=400, body='{"error":"缺少插件名"}')
        try:
            plugin_dir = self._find_plugin_dir(plugin_name)
            if plugin_dir:  # 已启用 → 禁用
                plugin_dir.rename(plugin_dir.with_name(plugin_dir.name + ".disabled"))
                enabled = False
            else:           # 已禁用 → 启用
                disabled_dir = self._find_disabled_plugin_dir(plugin_name)
                if not disabled_dir:
                    return Response(status=404, body='{"error":"插件未安装"}')
                disabled_dir.rename(disabled_dir.with_name(plugin_name))
                enabled = True
            return Response(status=200, headers={"Content-Type": "application/json"},
                            body=json.dumps({"ok": True, "success": True, "enabled": enabled}, ensure_ascii=False))
        except Exception as e:
            return Response(status=500, body=json.dumps({"error": str(e)}, ensure_ascii=False))

    def _handle_remote_store(self, request):
        """从 Gitee API 获取远程插件列表"""
        try:
            plugins = self._fetch_remote_plugins()
            return Response(status=200, headers={"Content-Type": "application/json"}, body=json.dumps(plugins, ensure_ascii=False))
        except Exception as e:
            return Response(status=500, body=json.dumps({"error": str(e)}))

    def _handle_store_install(self, request):
        """安装插件

        兼容两条路由：/api/store/install（body: name+author）与页面按钮 /api/plugins/install（body: plugin）
        未指定 author 时：优先启用本地已被禁用的同名插件，否则回退到官方命名空间远程安装。
        """
        try:
            body = self._body_json(request)
            name = body.get("name") or body.get("plugin") or ""
            if not name:
                return Response(status=400, body='{"error":"缺少插件名"}')
            author = body.get("author") or ""
            if author:
                success = self._install_from_gitee(name, author)
            else:
                disabled = self._find_disabled_plugin_dir(name)
                if disabled:
                    disabled.rename(disabled.with_name(name))
                    Log.info("pkg-manager", f"已启用本地插件: {name}")
                    success = True
                else:
                    success = self._install_from_gitee(name, "@{AstrumShell}")
            return Response(status=200, headers={"Content-Type": "application/json"},
                            body=json.dumps({"ok": success, "success": success}, ensure_ascii=False))
        except Exception as e:
            return Response(status=500, body=json.dumps({"error": str(e)}, ensure_ascii=False))

    # ==================== Gitee 远程商店 ====================

    def _fetch_remote_plugins(self) -> list:
        """从 Gitee 获取所有可用插件（带缓存+限速+重试）"""
        import time
        now = time.time()
        if self._remote_cache and (now - self._cache_time) < self._cache_ttl:
            return self._remote_cache

        plugins = []
        try:
            store_url = f"{GITEE_API_BASE}/store"
            # 重试 3 次，每次间隔增加
            for attempt in range(3):
                try:
                    with _gitee_request(store_url, timeout=15) as resp:
                        dirs = json.loads(resp.read().decode("utf-8"))
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(1 + attempt)
                        continue
                    raise

            time.sleep(0.5)

            for dir_info in dirs:
                if dir_info.get("type") != "dir":
                    continue
                author = dir_info.get("name", "")
                if not author.startswith("@{"):
                    continue

                author_url = f"{GITEE_API_BASE}/store/{urllib.parse.quote(author, safe='')}"
                for attempt in range(3):
                    try:
                        with _gitee_request(author_url, timeout=15) as resp:
                            plugin_dirs = json.loads(resp.read().decode("utf-8"))
                        break
                    except Exception as e:
                        import traceback; print(f"[main.py] 错误:{type(e).__name__}:{e}"); traceback.print_exc()
                        if attempt < 2:
                            time.sleep(1 + attempt)
                            continue
                        raise

                time.sleep(0.5)

                for plugin_dir in plugin_dirs:
                    if plugin_dir.get("type") != "dir":
                        continue
                    plugin_name = plugin_dir.get("name", "")

                    manifest_url = f"{GITEE_API_BASE}/store/{urllib.parse.quote(author, safe='')}/{plugin_name}/manifest.json"
                    manifest = {}
                    for attempt in range(3):
                        try:
                            with _gitee_request(manifest_url, timeout=15) as resp:
                                manifest = json.loads(resp.read().decode("utf-8"))
                            break
                        except Exception as e:
                            import traceback; print(f"[main.py] 错误:{type(e).__name__}:{e}"); traceback.print_exc()
                            if attempt < 2:
                                time.sleep(1 + attempt)
                                continue

                    plugins.append({
                        "name": plugin_name,
                        "author": author,
                        "full_name": f"{author}/{plugin_name}",
                        "metadata": manifest.get("metadata", {}),
                        "dependencies": manifest.get("dependencies", []),
                        "has_config": False,
                        "is_installed": self._is_plugin_installed(plugin_name, author)
                    })

                time.sleep(0.5)

            self._remote_cache = plugins
            self._cache_time = now
        except Exception as e:
            Log.error("pkg-manager", f"获取远程插件列表失败: {type(e).__name__}: {e}")

        return plugins

    def _install_from_gitee(self, plugin_name: str, author: str) -> bool:
        """从 Gitee 下载并安装插件（使用 raw URL）"""
        import shutil, time
        install_dir = self.store_dir / author / plugin_name
        install_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 获取目录结构（需要一次 API 调用）
            api_url = f"{GITEE_API_BASE}/store/{author}/{plugin_name}"
            with _gitee_request(api_url, timeout=15) as resp:
                items = json.loads(resp.read().decode("utf-8"))

            time.sleep(0.5)

            for item in items:
                if item.get("type") == "file":
                    # 使用 raw URL 下载文件（不走 API）
                    filename = item.get("name")
                    raw_url = f"{GITEE_RAW_BASE}/store/{author}/{plugin_name}/{filename}"
                    local_file = install_dir / filename
                    try:
                        with _gitee_request(raw_url, timeout=15) as resp:
                            content = resp.read()
                        with open(local_file, 'wb') as f:
                            f.write(content)
                    except:
                        pass
                elif item.get("type") == "dir":
                    sub_dir = item.get("name")
                    self._download_dir_raw(author, plugin_name, sub_dir, install_dir / sub_dir)
                    time.sleep(0.3)

            Log.info("pkg-manager", f"已安装: {author}/{plugin_name}")
            return True
        except Exception as e:
            Log.error("pkg-manager", f"安装失败 {plugin_name}: {type(e).__name__}: {e}")
            if install_dir.exists():
                shutil.rmtree(install_dir)
            return False

    def _download_dir_raw(self, author: str, plugin: str, sub_dir: str, local_dir: Path):
        """使用 raw URL 递归下载子目录"""
        import time
        try:
            api_url = f"{GITEE_API_BASE}/store/{author}/{plugin}/{sub_dir}"
            with _gitee_request(api_url, timeout=15) as resp:
                items = json.loads(resp.read().decode("utf-8"))

            local_dir.mkdir(parents=True, exist_ok=True)
            for item in items:
                if item.get("type") == "file":
                    filename = item.get("name")
                    raw_url = f"{GITEE_RAW_BASE}/store/{author}/{plugin}/{sub_dir}/{filename}"
                    try:
                        with _gitee_request(raw_url, timeout=15) as resp:
                            content = resp.read()
                        with open(local_dir / filename, 'wb') as f:
                            f.write(content)
                    except:
                        pass
                elif item.get("type") == "dir":
                    self._download_dir_raw(author, plugin, f"{sub_dir}/{item.get('name')}", local_dir / item.get("name"))
        except:
            pass

    # ==================== 辅助方法 ====================

    @staticmethod
    def _body_json(request) -> dict:
        """安全解析 JSON 请求体（无 body / 非法 JSON / 非对象时返回空字典）"""
        try:
            raw = getattr(request, "body", "") or ""
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", "replace")
            raw = raw.strip()
            if not raw:
                return {}
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _resolve_plugin_name(self, request) -> str:
        """插件名解析：兼容路径参数 /api/plugins/:name/... 与请求体 {"plugin"|"name": ...}"""
        params = getattr(request, "path_params", None) or {}
        name = params.get("name") or ""
        if not name:
            body = self._body_json(request)
            name = body.get("plugin") or body.get("name") or ""
        return name

    def _find_disabled_plugin_dir(self, plugin_name: str) -> Path | None:
        """查找已被禁用的插件目录（目录名以 .disabled 结尾）"""
        if not self.store_dir.exists():
            return None
        for author_dir in self.store_dir.iterdir():
            if not author_dir.is_dir():
                continue
            candidate = author_dir / f"{plugin_name}.disabled"
            if candidate.is_dir() and (candidate / "main.py").exists():
                return candidate
        return None

    def _iter_plugin_dirs(self):
        """遍历 store 下所有插件目录，产出 (作者目录名, 插件目录, 真实插件名, 是否启用)"""
        if not self.store_dir.exists():
            return
        for author_dir in sorted(self.store_dir.iterdir()):
            if not (author_dir.is_dir() and author_dir.name.startswith("@")):
                continue
            for plugin_dir in sorted(author_dir.iterdir()):
                if not plugin_dir.is_dir() or not (plugin_dir / "main.py").exists():
                    continue
                enabled = not plugin_dir.name.endswith(".disabled")
                name = plugin_dir.name if enabled else plugin_dir.name[: -len(".disabled")]
                yield author_dir.name, plugin_dir, name, enabled

    @staticmethod
    def _plugin_metadata(plugin_dir: Path) -> dict:
        """读取 manifest.json 的 metadata（失败时返回空字典）"""
        manifest_path = plugin_dir / "manifest.json"
        if not manifest_path.exists():
            return {}
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return (json.load(f) or {}).get("metadata", {}) or {}
        except Exception:
            return {}

    def _get_installed_plugins(self) -> dict:
        """已安装插件：{插件名: {enabled, version, author, full_name}}（供插件管理页渲染）"""
        result = {}
        for author, plugin_dir, name, enabled in self._iter_plugin_dirs():
            meta = self._plugin_metadata(plugin_dir)
            result[name] = {
                "enabled": enabled,
                "version": meta.get("version", "未知"),
                "author": meta.get("author", author),
                "full_name": f"{author}/{name}",
            }
        return result

    def _get_available_plugins(self) -> dict:
        """可安装插件：本地 store 中所有插件（含被禁用的）

        远程商店由 /api/store/remote 提供，这里只列本地，避免页面渲染依赖网络。
        """
        result = {}
        for author, plugin_dir, name, _enabled in self._iter_plugin_dirs():
            meta = self._plugin_metadata(plugin_dir)
            result[name] = {
                "name": meta.get("name", name),
                "description": meta.get("description", "暂无描述"),
                "version": meta.get("version", "未知"),
                "author": meta.get("author", author),
            }
        return result

    def _scan_all_plugins(self) -> list:
        """扫描本地已安装插件"""
        plugins = []
        if not self.store_dir.exists():
            return plugins

        for author_dir in self.store_dir.iterdir():
            if author_dir.is_dir() and author_dir.name.startswith("@{"):
                for plugin_dir in author_dir.iterdir():
                    if plugin_dir.is_dir() and (plugin_dir / "main.py").exists():
                        manifest_path = plugin_dir / "manifest.json"
                        if manifest_path.exists():
                            with open(manifest_path, 'r', encoding='utf-8') as f:
                                manifest = json.load(f)
                            # 目录名带 .disabled 后缀表示被禁用：对外统一去掉后缀并标注状态
                            enabled = not plugin_dir.name.endswith(".disabled")
                            name = plugin_dir.name if enabled else plugin_dir.name[: -len(".disabled")]
                            plugins.append({
                                "name": name,
                                "full_name": f"{author_dir.name}/{name}",
                                "author": author_dir.name,
                                "metadata": manifest.get("metadata", {}),
                                "dependencies": manifest.get("dependencies", []),
                                "has_config": (plugin_dir / "config.json").exists(),
                                "enabled": enabled,
                                "is_installed": True
                            })
        return plugins

    def _is_plugin_installed(self, plugin_name: str, author: str) -> bool:
        """检查插件是否已安装"""
        plugin_dir = self.store_dir / author / plugin_name
        return (plugin_dir / "main.py").exists()

    def _find_plugin_dir(self, plugin_name: str) -> Path | None:
        """查找插件目录"""
        if not self.store_dir.exists():
            return None
        for author_dir in self.store_dir.iterdir():
            if author_dir.is_dir():
                plugin_dir = author_dir / plugin_name
                if plugin_dir.exists() and (plugin_dir / "main.py").exists():
                    return plugin_dir
        return None

    def _load_config_schema(self, plugin_name: str) -> dict:
        """加载插件 config.json schema"""
        plugin_dir = self._find_plugin_dir(plugin_name)
        if not plugin_dir:
            return {}
        schema_path = plugin_dir / "config.json"
        if not schema_path.exists():
            return {}
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_plugin_config(self, plugin_name: str) -> dict:
        """加载插件当前配置"""
        schema = self._load_config_schema(plugin_name)
        defaults = {}
        for key, field_def in schema.items():
            defaults[key] = field_def.get("default")
        if self.storage:
            storage_instance = self.storage.get_storage("pkg-manager")
            user_config = storage_instance.get(f"plugin_config.{plugin_name}", {})
            defaults.update(user_config)
        return defaults

    def _save_plugin_config(self, plugin_name: str, config: dict):
        """保存插件配置"""
        if self.storage:
            storage_instance = self.storage.get_storage("pkg-manager")
            storage_instance.set(f"plugin_config.{plugin_name}", config)

    def _get_plugin_detailed_info(self, plugin_name: str) -> dict:
        """获取插件的依赖、事件、页面信息"""
        dependencies = []
        events = []  # 事件 = 功能描述
        plugin_dir = self._find_plugin_dir(plugin_name)
        
        if plugin_dir:
            manifest_path = plugin_dir / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                dependencies = manifest.get("dependencies", [])
                # 从 manifest 的 metadata.description 或 type 中提取功能
                metadata = manifest.get("metadata", {})
                plugin_type = metadata.get("type", "")
                if plugin_type:
                    events.append(f"类型: {plugin_type}")
                # 从 manifest config 推断功能
                config = manifest.get("config", {})
                if config.get("enabled"):
                    events.append("已启用")

        # 只返回该插件自己注册的页面（通过插件名匹配）
        pages = []
        if self.webui and hasattr(self.webui, 'server') and self.webui.server:
            for path, provider in self.webui.server.pages.items():
                # 检查 provider 是否属于该插件
                provider_name = getattr(provider, '__self__', None)
                if provider_name and isinstance(provider_name, PkgManagerPlugin):
                    continue  # 跳过自己的页面
                # 通过路径前缀判断（dashboard 注册 /dashboard）
                if path == f'/{plugin_name}' or path.startswith(f'/{plugin_name}/'):
                    pages.append({"path": path})
                # 特殊处理：首页
                if plugin_name == 'webui' and path == '/':
                    pages.append({"path": path})

        return {
            "name": plugin_name,
            "dependencies": dependencies,
            "config_fields": list(self._load_config_schema(plugin_name).keys()),
            "pages": pages,
            "events": events
        }


register_plugin_type("PkgManagerPlugin", PkgManagerPlugin)


def New():
    return PkgManagerPlugin()
