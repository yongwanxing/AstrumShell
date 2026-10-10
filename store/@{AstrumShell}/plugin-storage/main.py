"""插件存储插件入口 - 统一文件读写服务"""
import json
import threading
import mimetypes
import shutil
from pathlib import Path
from typing import Any, Optional, BinaryIO
from datetime import datetime

from oss.logger.logger import Log
from oss.plugin.types import Plugin, register_plugin_type, Response
from oss.config import get_config


class PluginStorage:
    """插件隔离存储 - 每个插件拥有独立的 data/<plugin_name>/ 目录"""

    def __init__(self, plugin_name: str, data_dir: str = None):
        config = get_config()
        self.plugin_name = plugin_name
        self.data_dir = Path(data_dir or str(config.data_dir)) / plugin_name
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._load()

    # ========== JSON 键值存储 ==========

    def _load(self):
        """加载 JSON 存储数据"""
        data_file = self.data_dir / "data.json"
        if data_file.exists():
            try:
                with open(data_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        self._data = json.loads(content)
                    else:
                        self._data = {}
            except (json.JSONDecodeError, IOError) as e:
                Log.error("plugin-storage", f"加载数据失败 {self.plugin_name}: {e}")
                self._data = {}

    def _save(self):
        """保存 JSON 存储数据"""
        data_file = self.data_dir / "data.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """获取 JSON 值"""
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any):
        """设置 JSON 值"""
        with self._lock:
            self._data[key] = value
            self._save()

    def delete(self, key: str) -> bool:
        """删除 JSON 键"""
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._save()
                return True
            return False

    def has(self, key: str) -> bool:
        """检查 JSON 键是否存在"""
        with self._lock:
            return key in self._data

    def keys(self) -> list[str]:
        """获取所有 JSON 键"""
        with self._lock:
            return list(self._data.keys())

    def clear(self):
        """清空 JSON 存储"""
        with self._lock:
            self._data.clear()
            self._save()

    def size(self) -> int:
        """获取 JSON 存储大小（键数量）"""
        with self._lock:
            return len(self._data)

    def get_all(self) -> dict[str, Any]:
        """获取所有 JSON 数据"""
        with self._lock:
            return self._data.copy()

    def set_many(self, data: dict[str, Any]):
        """批量设置 JSON"""
        with self._lock:
            self._data.update(data)
            self._save()

    def get_meta(self) -> dict[str, Any]:
        """获取存储元信息"""
        return {
            "plugin": self.plugin_name,
            "keys": self.size(),
            "path": str(self.data_dir),
        }

    # ========== 文件级别操作 ==========

    def read_file(self, path: str, mode: str = "r") -> Optional[str | bytes]:
        """读取插件目录内的文件
        
        Args:
            path: 相对于插件数据目录的路径，如 "index.html" 或 "templates/home.html"
            mode: "r" (文本) 或 "rb" (二进制)
        
        Returns:
            文件内容，文件不存在时返回 None
        """
        try:
            file_path = self._resolve_path(path)
            if not file_path.exists() or not file_path.is_file():
                return None
            with open(file_path, mode, encoding="utf-8" if mode == "r" else None) as f:
                return f.read()
        except Exception as e:
            Log.error("plugin-storage", f"读取文件失败 {self.plugin_name}/{path}: {type(e).__name__}: {e}")
            return None

    def write_file(self, path: str, content: str | bytes):
        """写入文件到插件目录
        
        Args:
            path: 相对于插件数据目录的路径
            content: 文件内容（字符串或字节）
        """
        try:
            file_path = self._resolve_path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                with open(file_path, "wb") as f:
                    f.write(content)
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
        except Exception as e:
            Log.error("plugin-storage", f"写入文件失败 {self.plugin_name}/{path}: {type(e).__name__}: {e}")

    def delete_file(self, path: str) -> bool:
        """删除插件目录内的文件"""
        try:
            file_path = self._resolve_path(path)
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception as e:
            Log.error("plugin-storage", f"删除文件失败 {self.plugin_name}/{path}: {type(e).__name__}: {e}")
            return False

    def list_files(self, prefix: str = "") -> list[str]:
        """列出插件目录内的文件
        
        Args:
            prefix: 子目录前缀，如 "templates/" 或 ""（全部）
        
        Returns:
            相对路径列表
        """
        try:
            search_dir = self._resolve_path(prefix) if prefix else self.data_dir
            if not search_dir.exists():
                return []
            files = []
            for f in search_dir.rglob("*"):
                if f.is_file():
                    files.append(str(f.relative_to(self.data_dir)))
            return sorted(files)
        except Exception as e:
            Log.error("plugin-storage", f"列出文件失败：{type(e).__name__}: {e}")
            return []

    def file_exists(self, path: str) -> bool:
        """检查文件是否存在"""
        try:
            file_path = self._resolve_path(path)
            return file_path.exists() and file_path.is_file()
        except Exception as e:
            Log.error("plugin-storage", f"检查文件存在性失败：{type(e).__name__}: {e}")
            return False

    def serve_file(self, path: str) -> Response:
        """提供文件服务（返回 HTTP Response）
        
        用于插件向外部提供静态文件。
        自动检测 MIME 类型，支持文本和二进制文件。
        
        Args:
            path: 相对于插件数据目录的路径
        
        Returns:
            Response 对象（200 成功 / 404 不存在 / 403 安全拦截）
        """
        try:
            file_path = self._resolve_path(path)
            
            # 安全检查：防止目录遍历
            try:
                file_path.resolve().relative_to(self.data_dir.resolve())
            except ValueError:
                return Response(status=403, body="Forbidden: path traversal detected")

            if not file_path.exists() or not file_path.is_file():
                return Response(status=404, body=f"File not found: {path}")

            # 检测 MIME 类型
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = "application/octet-stream"

            # 读取文件内容
            if content_type.startswith("text/") or content_type in (
                "application/json", "application/javascript", "application/xml",
                "text/css", "text/html", "image/svg+xml"
            ):
                content = file_path.read_text(encoding="utf-8")
            else:
                content = file_path.read_bytes()

            return Response(
                status=200,
                headers={
                    "Content-Type": content_type,
                    "Cache-Control": "public, max-age=3600",
                },
                body=content,
            )
        except Exception as e:
            return Response(status=500, body=f"Error serving file: {e}")

    def _resolve_path(self, path: str) -> Path:
        """解析相对于插件数据目录的安全路径"""
        return (self.data_dir / path).resolve()

    def get_data_dir(self) -> Path:
        """获取插件数据目录绝对路径"""
        return self.data_dir.resolve()


class SharedStorage:
    """共享存储（供 plugin-bridge 使用）"""

    def __init__(self, storage_manager, shared_dir: Path = None):
        self._manager = storage_manager
        self._shared_dir = shared_dir or Path("./data/DCIM")
        self._shared_dir.mkdir(parents=True, exist_ok=True)

    def get_plugin_storage(self, plugin_name: str) -> PluginStorage:
        """获取指定插件的存储空间"""
        return self._manager.get_storage(plugin_name)

    def get_shared(self, key: str, default: Any = None) -> Any:
        """获取共享存储 (DCIM)"""
        shared_file = self._shared_dir / f"{key}.json"
        if shared_file.exists():
            with open(shared_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return default

    def set_shared(self, key: str, value: Any):
        """设置共享存储 (DCIM)"""
        shared_file = self._shared_dir / f"{key}.json"
        with open(shared_file, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)

    def list_storages(self) -> list[str]:
        """列出所有有存储的插件"""
        return self._manager.list_storages()


class PluginStoragePlugin(Plugin):
    """插件存储插件 - 所有插件的唯一文件读写入口"""

    def __init__(self):
        self.storages: dict[str, PluginStorage] = {}
        self.shared = None
        self.config = {}
        self.data_root = Path("./data")

    def init(self, deps: dict = None):
        """初始化 - 读取 config.json 配置"""
        self._load_config()

    def start(self):
        """启动"""
        Log.info("plugin-storage", f"插件存储服务已启动 (root={self.data_root})")

    def stop(self):
        """停止"""
        pass

    def _load_config(self):
        """读取 config.json 配置"""
        config_path = Path("./data/plugin-storage/config.json")
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            self.data_root = Path(self.config.get("data_root", "./data"))
            shared_dir_name = self.config.get("shared_dir", "DCIM")
            shared_dir = self.data_root / shared_dir_name
        else:
            Log.warn("plugin-storage", "config.json 不存在，使用默认配置")
            self.config = {"data_root": "./data", "shared_dir": "DCIM"}
            self.data_root = Path("./data")
            shared_dir = self.data_root / "DCIM"

        self.shared = SharedStorage(self, shared_dir=shared_dir)

    def get_storage(self, plugin_name: str) -> PluginStorage:
        """获取插件的隔离存储空间（唯一入口）"""
        if plugin_name not in self.storages:
            self.storages[plugin_name] = PluginStorage(
                plugin_name,
                data_dir=str(self.data_root)
            )
        return self.storages[plugin_name]

    def remove_storage(self, plugin_name: str) -> bool:
        """删除插件的存储空间"""
        if plugin_name in self.storages:
            del self.storages[plugin_name]
            data_dir = PluginStorage(plugin_name).data_dir
            if data_dir.exists():
                shutil.rmtree(data_dir)
            return True
        return False

    def list_storages(self) -> list[str]:
        """列出所有有存储的插件"""
        return list(self.storages.keys())

    def get_shared(self) -> SharedStorage:
        """获取共享存储接口"""
        return self.shared


# 注册类型
register_plugin_type("PluginStorage", PluginStorage)
register_plugin_type("SharedStorage", SharedStorage)


def New():
    return PluginStoragePlugin()
