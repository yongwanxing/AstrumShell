"""插件管理器 - 只加载 plugin-loader，其他所有插件由 plugin-loader 插件自行管理"""
from typing import Any, Optional

from oss.plugin.loader import PluginLoader

# 深度隐藏的成就系统导入
try:
    from oss.core.achievements import get_validator
    _ACHIEVEMENTS_ENABLED = True
except ImportError:
    _ACHIEVEMENTS_ENABLED = False


class PluginManager:
    """极简插件管理器
    
    遵循「最小化核心框架」设计哲学：
    - 核心框架只负责加载 plugin-loader 插件
    - 所有其他插件（HTTP、WebSocket、Dashboard 等）都由 plugin-loader 插件扫描和加载
    - store/@{AstrumShell}/ 是唯一的插件来源
    """

    def __init__(self):
        self.loader = PluginLoader()
        self.plugin_loader: Optional[Any] = None

    def load(self):
        """仅加载 plugin-loader 核心插件
        
        plugin-loader 插件会负责：
        1. 扫描 store/@{AstrumShell}/ 目录
        2. 加载所有启用的插件
        3. 处理依赖关系
        4. 执行 PL 注入机制
        """
        # 只加载 plugin-loader，其他所有插件都由它来管理
        pl_info = self.loader.load_core_plugin("plugin-loader")
        if pl_info:
            self.plugin_loader = pl_info["instance"]
        
        # 隐藏成就：深海潜水员 - 当加载插件管理器时解锁
        if _ACHIEVEMENTS_ENABLED:
            try:
                validator = get_validator()
                validator.unlock("deep_diver")
            except Exception:
                pass

    def start(self):
        """启动 plugin-loader，它会初始化并启动所有其他插件"""
        import time
        start_time = time.time()
        
        if self.plugin_loader:
            # plugin-loader.init() 会扫描并加载 store/ 中的所有插件
            self.plugin_loader.init()
            # plugin-loader.start() 会按依赖顺序启动所有插件
            self.plugin_loader.start()
        
        # 计算启动时间并检查速度成就
        elapsed_ms = (time.time() - start_time) * 1000
        if _ACHIEVEMENTS_ENABLED:
            try:
                validator = get_validator()
                validator.check_startup_speed(elapsed_ms)
                
                # 检查插件数量成就
                if hasattr(self.plugin_loader, 'manager') and hasattr(self.plugin_loader.manager, 'plugins'):
                    plugin_count = len(self.plugin_loader.manager.plugins)
                    validator.check_plugin_count(plugin_count)
            except Exception:
                pass

    def stop(self):
        """停止所有插件（由 plugin-loader 统一管理）"""
        if self.plugin_loader:
            try:
                self.plugin_loader.stop()
            except KeyboardInterrupt:
                print("[PluginManager] 用户中断停止过程")
            except Exception as e:
                import traceback
                print(f"[PluginManager] 停止插件时出错：{type(e).__name__}: {e}")
                traceback.print_exc()
            
            # 隐藏成就：崩溃幸存者 - 如果正常停止则不解锁，只有异常停止才可能解锁
            # 这里我们记录停止事件，用于将来可能的连续运行成就
            if _ACHIEVEMENTS_ENABLED:
                try:
                    validator = get_validator()
                    # 记录会话结束
                    validator.track_progress("session_end")
                except Exception:
                    pass
