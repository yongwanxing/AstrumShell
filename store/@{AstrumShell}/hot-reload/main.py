"""热插拔插件 - 运行时加载/卸载/更新插件"""
import sys
import time
import threading
from pathlib import Path
from typing import Any, Optional, Callable

from oss.logger.logger import Log
from oss.plugin.types import Plugin, register_plugin_type


class HotReloadError(Exception):
    """热插拔错误"""
    pass


class FileWatcher:
    """文件监听器"""

    def __init__(self, watch_dirs: list[str], extensions: list[str], on_change: Callable):
        self.watch_dirs = [Path(d) for d in watch_dirs]
        self.extensions = extensions
        self.on_change = on_change
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._file_times: dict[str, float] = {}
        self._scan_files()

    def _scan_files(self):
        """扫描当前文件及其修改时间"""
        for watch_dir in self.watch_dirs:
            if watch_dir.exists():
                for f in watch_dir.rglob("*"):
                    if f.is_file() and f.suffix in self.extensions:
                        self._file_times[str(f)] = f.stat().st_mtime

    def start(self):
        """开始监听"""
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止监听"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _watch_loop(self):
        """监听循环"""
        while self._running:
            changed = []
            current_files = {}

            for watch_dir in self.watch_dirs:
                if watch_dir.exists():
                    for f in watch_dir.rglob("*"):
                        if f.is_file() and f.suffix in self.extensions:
                            fpath = str(f)
                            mtime = f.stat().st_mtime
                            current_files[fpath] = mtime

                            # 新文件或修改过
                            if fpath not in self._file_times:
                                changed.append(("new", f))
                            elif mtime > self._file_times[fpath]:
                                changed.append(("modified", f))

            # 检查删除的文件
            for fpath in self._file_times:
                if fpath not in current_files:
                    changed.append(("deleted", Path(fpath)))

            if changed:
                self._file_times = current_files
                self.on_change(changed)

            time.sleep(1)


class HotReloadPlugin(Plugin):
    """热插拔插件"""

    def __init__(self):
        self.plugin_loader_instance = None
        self.watcher: Optional[FileWatcher] = None
        self.watch_dirs: list[str] = []
        self.watch_extensions: list[str] = [".py", ".json"]

    def init(self, deps: dict = None):
        """初始化"""
        pass

    def start(self):
        """启动 - 自动开始监听默认目录"""
        if not self.watch_dirs:
            # 默认监听 store 目录
            self.watch_dirs = ["store"]
        self.start_watching()

    def stop(self):
        """停止"""
        if self.watcher:
            self.watcher.stop()

    def set_plugin_loader(self, plugin_loader):
        """设置插件加载器实例"""
        self.plugin_loader_instance = plugin_loader

    def set_watch_dirs(self, dirs: list[str]):
        """设置监听目录"""
        self.watch_dirs = dirs

    def start_watching(self):
        """开始监听文件变化"""
        if self.watch_dirs and self.plugin_loader_instance:
            self.watcher = FileWatcher(
                self.watch_dirs,
                self.watch_extensions,
                self._on_file_change
            )
            self.watcher.start()

    def _on_file_change(self, changes: list[tuple[str, Path]]):
        """文件变化回调"""
        for change_type, fpath in changes:
            # 只关心 main.py 和 manifest.json 的变化
            if fpath.name not in ("main.py", "manifest.json"):
                continue

            plugin_dir = fpath.parent
            plugin_name = plugin_dir.name

            try:
                if change_type == "new":
                    self.load_plugin(plugin_dir)
                elif change_type == "modified":
                    self.reload_plugin(plugin_name, plugin_dir)
                elif change_type == "deleted":
                    self.unload_plugin(plugin_name)
            except Exception as e:
                Log.error("hot-reload", f"处理变化失败: {type(e).__name__}: {e}")

    def load_plugin(self, plugin_dir: Path) -> bool:
        """运行时加载插件"""
        try:
            plugin_name = plugin_dir.name
            if plugin_name in self.plugin_loader_instance.plugins:
                raise HotReloadError(f"插件已存在: {plugin_name}")

            self.plugin_loader_instance.load(plugin_dir)
            info = self.plugin_loader_instance.plugins[plugin_name]
            instance = info["instance"]
            instance.init()
            instance.start()
            return True
        except Exception as e:
            raise HotReloadError(f"加载插件失败: {e}")

    def unload_plugin(self, plugin_name: str) -> bool:
        """运行时卸载插件"""
        try:
            if plugin_name not in self.plugin_loader_instance.plugins:
                raise HotReloadError(f"插件不存在: {plugin_name}")

            info = self.plugin_loader_instance.plugins[plugin_name]
            instance = info["instance"]
            instance.stop()

            # 从模块缓存中移除
            module = info.get("module")
            if module and module.__name__ in sys.modules:
                del sys.modules[module.__name__]

            del self.plugin_loader_instance.plugins[plugin_name]
            return True
        except Exception as e:
            raise HotReloadError(f"卸载插件失败: {e}")

    def reload_plugin(self, plugin_name: str, plugin_dir: Path) -> bool:
        """运行时更新插件"""
        try:
            # 先卸载
            self.unload_plugin(plugin_name)
            # 再加载
            return self.load_plugin(plugin_dir)
        except Exception as e:
            raise HotReloadError(f"更新插件失败: {e}")


# 注册类型
register_plugin_type("HotReloadError", HotReloadError)
register_plugin_type("FileWatcher", FileWatcher)


def New():
    return HotReloadPlugin()
