"""插件加载器 - 专门用于加载核心插件

遵循「最小化核心框架」设计哲学：
- 只负责加载可信的核心插件（来自 store/@{AstrumShell}/）
- 所有插件都使用统一的加载机制
- 不再区分沙箱模式和非沙箱模式
"""
import sys
import importlib.util
from pathlib import Path
from typing import Any, Optional, Dict

from oss.config import get_config


class PluginLoader:
    """插件加载器 - 专门用于加载核心插件
    
    遵循「最小化核心框架」设计哲学：
    - 只负责加载可信的核心插件（来自 store/@{AstrumShell}/）
    - 所有插件都使用统一的加载机制
    - 不再区分沙箱模式和非沙箱模式
    """

    def __init__(self):
        self.loaded: dict[str, Any] = {}
        self._config = get_config()

    def load_core_plugin(self, plugin_name: str, store_dir: Optional[str] = None) -> Optional[dict[str, Any]]:
        """加载核心插件（来自 store/@{AstrumShell}/）
        
        Args:
            plugin_name: 插件名称（如 "plugin-loader"）
            store_dir: 插件仓库目录，默认使用配置中的 STORE_DIR
            
        Returns:
            插件信息字典，包含 instance、module、path、name
        """
        if store_dir is None:
            store_dir = str(self._config.store_dir)
        plugin_dir = Path(store_dir) / "@{AstrumShell}" / plugin_name
        return self._load_plugin(plugin_name, plugin_dir)

    def _load_plugin(self, plugin_name: str, plugin_dir: Path) -> Optional[dict[str, Any]]:
        """加载插件（内部方法）
        
        Args:
            plugin_name: 插件名称
            plugin_dir: 插件目录路径
            
        Returns:
            插件信息字典，如果加载失败则返回 None
        """
        if not (plugin_dir / "main.py").exists():
            print(f"[PluginLoader] 插件不存在：{plugin_dir}")
            return None

        # 清理插件名（去掉 } 等）
        clean_name = plugin_name.rstrip("}")
        module_name = f"plugin.{clean_name}"
        spec = importlib.util.spec_from_file_location(module_name, str(plugin_dir / "main.py"))
        module = importlib.util.module_from_spec(spec)
        module.__package__ = module_name
        module.__path__ = [str(plugin_dir)]  # 启用相对导入子模块
        sys.modules[spec.name] = module

        # 执行模块（核心插件是可信的，不需要沙箱）
        try:
            spec.loader.exec_module(module)
        except SyntaxError as e:
            print(f"[PluginLoader] 插件 {clean_name} 语法错误：{e}")
            import traceback
            traceback.print_exc()
            return None
        except ImportError as e:
            print(f"[PluginLoader] 插件 {clean_name} 导入错误：{e}")
            import traceback
            traceback.print_exc()
            return None
        except Exception as e:
            print(f"[PluginLoader] 加载插件 {clean_name} 失败：{type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None

        if not hasattr(module, "New"):
            print(f"[PluginLoader] 插件 {clean_name} 缺少 New() 函数")
            return None

        try:
            instance = module.New()
        except TypeError as e:
            print(f"[PluginLoader] 创建插件 {clean_name} 实例失败：参数错误 - {e}")
            return None
        except Exception as e:
            print(f"[PluginLoader] 创建插件 {clean_name} 实例失败：{type(e).__name__}: {e}")
            return None

        self.loaded[clean_name] = {
            "instance": instance,
            "module": module,
            "path": str(plugin_dir),
            "name": clean_name,
        }
        return self.loaded[clean_name]
