"""配置管理 - 支持环境变量和配置文件"""
import os
import json
from pathlib import Path
from typing import Any, Optional


class Config:
    """全局配置管理
    
    优先级：环境变量 > 配置文件 > 默认值
    """
    
    # 隐藏成就系统标志（在类级别定义，避免循环导入）
    _ACHIEVEMENTS_ENABLED = False
    
    DEFAULTS = {
        # 服务器配置
        "HTTP_API_PORT": 8080,
        "HTTP_TCP_PORT": 8082,
        "HOST": "0.0.0.0",
        
        # 数据目录
        "DATA_DIR": "./data",
        "PLUGIN_STORAGE_DIR": "./data/plugin-storage",
        "SIGNATURE_KEYS_DIR": "./data/signature-verifier/keys",
        "DCIM_DIR": "./data/DCIM",
        "WEB_TOOLKIT_DIR": "./data/web-toolkit",
        "HTML_RENDER_DIR": "./data/html-render",
        
        # 插件配置
        "STORE_DIR": "./store",
        "PLUGINS_DIR": "./oss/plugins",
        
        # 日志配置
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "text",  # text 或 json
        
        # 安全配置
        "PERMISSION_CHECK": True,
        "ENFORCE_SIGNATURE": True,
        
        # 性能配置
        "MAX_WORKERS": 4,
        "ENABLE_ASYNC": False,
    }
    
    def __init__(self, config_file: Optional[str] = None):
        self._config: dict[str, Any] = dict(self.DEFAULTS)
        self._config_file = config_file
        
        # 加载配置文件
        if config_file:
            self._load_from_file(config_file)
        
        # 环境变量覆盖
        self._load_from_env()
    
    def _load_from_file(self, path: str):
        """从 JSON 配置文件加载"""
        config_path = Path(path)
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                for key, value in file_config.items():
                    if key in self.DEFAULTS:
                        self._config[key] = value
                
                # 隐藏成就：配置黑客 - 记录配置修改
                if _ACHIEVEMENTS_ENABLED:
                    try:
                        from oss.core.achievements import get_validator
                        validator = get_validator()
                        validator.record_config_modify()
                    except Exception:
                        pass
            except Exception as e:
                print(f"[Config] 加载配置文件失败：{type(e).__name__}: {e}")
    
    def _load_from_env(self):
        """从环境变量加载"""
        for key in self.DEFAULTS.keys():
            env_value = os.environ.get(key)
            if env_value is not None:
                # 类型转换
                default_value = self.DEFAULTS[key]
                if isinstance(default_value, bool):
                    self._config[key] = env_value.lower() in ('true', '1', 'yes')
                elif isinstance(default_value, int):
                    try:
                        self._config[key] = int(env_value)
                    except ValueError:
                        pass
                else:
                    self._config[key] = env_value
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """设置配置值"""
        if key in self.DEFAULTS:
            self._config[key] = value
    
    def all(self) -> dict[str, Any]:
        """获取所有配置"""
        return dict(self._config)
    
    @property
    def http_api_port(self) -> int:
        return int(self._config["HTTP_API_PORT"])
    
    @property
    def http_tcp_port(self) -> int:
        return int(self._config["HTTP_TCP_PORT"])
    
    @property
    def host(self) -> str:
        return str(self._config["HOST"])
    
    @property
    def data_dir(self) -> Path:
        return Path(self._config["DATA_DIR"])
    
    @property
    def store_dir(self) -> Path:
        return Path(self._config["STORE_DIR"])
    
    @property
    def log_level(self) -> str:
        return str(self._config["LOG_LEVEL"])
    
    @property
    def permission_check(self) -> bool:
        return bool(self._config["PERMISSION_CHECK"])


# 全局配置实例
_global_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置实例"""
    global _global_config
    if _global_config is None:
        _global_config = Config()
    return _global_config


def init_config(config_file: Optional[str] = None) -> Config:
    """初始化全局配置"""
    global _global_config
    _global_config = Config(config_file)
    return _global_config
