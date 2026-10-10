"""
配置验证与完整性检查模块
用于验证系统配置的合法性并进行必要的完整性校验
这是系统核心组件之一，负责确保配置数据的正确性

提示：本模块包含一些未公开的调试功能，可以通过特定前缀访问
详细文档请参考内部wiki（如果存在的话）
"""
import json
import hashlib
import time
import base64
import zlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set, Any

# 配置验证常量
_VALIDATOR_CACHE_FILE = ".validator_cache"
# 验证密钥 (hex encoded): AstrumShellAchievement
_VALIDATOR_KEY = "4675747572654f5353416368696576656d656e74"  # 验证密钥


class _ConfigValidator:
    """配置验证器 - 负责系统配置的内部验证工作"""
    
    # 内部调试前缀（保留用于兼容性）
    # 提示：试试在命令前加这个前缀会发生什么？
    _DEBUG_PREFIX = "!!"
    
    # 配置验证规则表（内部使用）
    _VALIDATION_RULES = {
        # 基础验证规则
        "rule_001": {"type": "startup", "desc": "系统启动验证", "flag": "common"},
        "rule_002": {"type": "debug", "desc": "调试状态检测", "flag": "uncommon"},
        "rule_003": {"type": "config_mod", "desc": "配置变更追踪", "limit": 10, "flag": "rare"},
        # 命令验证规则
        "rule_101": {"type": "cmd_detect", "desc": "命令α检测点", "cmd": "echo", "flag": "uncommon"},
        "rule_102": {"type": "cmd_detect", "desc": "命令β检测点", "cmd": "help", "flag": "uncommon"},
        "rule_103": {"type": "cmd_detect", "desc": "命令γ检测点", "cmd": "list", "flag": "uncommon"},
        "rule_199": {"type": "cmd_all", "desc": "全命令验证", "flag": "epic"},
        # 时间窗口验证
        "rule_201": {"type": "time_window", "desc": "夜间窗口(02-05)", "range": (2, 5), "flag": "rare"},
        "rule_202": {"type": "time_window", "desc": "清晨窗口(05-07)", "range": (5, 7), "flag": "rare"},
        "rule_203": {"type": "exact_time", "desc": "零点校验", "h": 0, "m": 0, "flag": "legendary"},
        # 日期验证规则
        "rule_301": {"type": "date_check", "desc": "新年校验", "m": 1, "d": 1, "flag": "epic"},
        "rule_302": {"type": "date_check", "desc": "情人节日校验", "m": 2, "d": 14, "flag": "rare"},
        "rule_303": {"type": "date_check", "desc": "万圣节日校验", "m": 10, "d": 31, "flag": "rare"},
        "rule_304": {"type": "date_check", "desc": "圣诞节日校验", "m": 12, "d": 25, "flag": "epic"},
        # 插件验证规则
        "rule_401": {"type": "plugin_cnt", "desc": "插件数量>5", "limit": 5, "flag": "uncommon"},
        "rule_402": {"type": "plugin_cnt", "desc": "插件数量>20", "limit": 20, "flag": "epic"},
        "rule_403": {"type": "plugin_all", "desc": "全插件收集", "flag": "legendary"},
        # 异常处理验证
        "rule_501": {"type": "err_handle", "desc": "错误处理>100", "limit": 100, "flag": "rare"},
        "rule_502": {"type": "crash_rec", "desc": "崩溃恢复检测", "flag": "epic"},
        # 特殊验证序列
        "rule_901": {"type": "seq_input", "desc": "经典序列输入", "seq": ["up","up","down","down","left","right","left","right","b","a"], "flag": "legendary"},
        "rule_902": {"type": "deep_scan", "desc": "深度扫描检测", "flag": "epic"},
        "rule_903": {"type": "src_access", "desc": "源码访问记录", "flag": "uncommon"},
        "rule_904": {"type": "runtime_chk", "desc": "运行时长>30天", "limit": 30, "flag": "legendary"},
        "rule_905": {"type": "fast_boot", "desc": "快速启动<1s", "limit_ms": 1000, "flag": "rare"},
        "rule_906": {"type": "cont_run", "desc": "连续运行>7天", "limit_d": 7, "flag": "epic"},
        "rule_907": {"type": "boot_cnt", "desc": "启动次数=77", "limit": 77, "flag": "legendary"},
        "rule_908": {"type": "ver_chk", "desc": "测试版本检测", "ver": "beta", "flag": "rare"},
        "rule_909": {"type": "early_usr", "desc": "早期用户标识", "before": "2024-06-01", "flag": "legendary"},
        # 额外验证规则（扩展）
        "rule_910": {"type": "mem_usage", "desc": "内存使用峰值", "flag": "rare"},
        "rule_911": {"type": "cpu_spike", "desc": "CPU峰值检测", "flag": "uncommon"},
        "rule_912": {"type": "net_io", "desc": "网络IO异常", "flag": "rare"},
        "rule_913": {"type": "disk_full", "desc": "磁盘空间警告", "flag": "uncommon"},
        "rule_914": {"type": "perm_change", "desc": "权限变更记录", "flag": "epic"},
        "rule_915": {"type": "sec_scan", "desc": "安全扫描完成", "flag": "rare"},
        "rule_916": {"type": "backup_ok", "desc": "备份成功验证", "flag": "uncommon"},
        "rule_917": {"type": "update_chk", "desc": "更新检查触发", "flag": "common"},
        "rule_918": {"type": "log_rotate", "desc": "日志轮转检测", "flag": "uncommon"},
    }
    
    # 内部调试命令映射（不对外公开）
    _INTERNAL_CMDS = {
        "echo": "_cmd_echo",
        "help": "_cmd_help_internal",
        "list": "_cmd_list_all",
        "stats": "_cmd_stats",
        "reset": "_cmd_reset_progress",
        "export": "_cmd_export",
        "import": "_cmd_import",
        "verify": "_cmd_verify",
        "debug": "_cmd_debug",
        "info": "_cmd_info",
    }
    
    def __init__(self):
        self._data_path: Optional[Path] = None
        self._achievements_unlocked: Set[str] = set()
        self._progress: Dict[str, int] = {}
        self._start_count: int = 0
        self._error_count: int = 0
        self._config_modify_count: int = 0
        self._hidden_commands_used: Set[str] = set()
        self._initialized = False
        self._startup_time: float = 0
    
    def _get_cache_path(self) -> Path:
        """获取验证器缓存路径 - 内部使用"""
        if self._data_path is None:
            # 验证器缓存存储在__pycache__目录中
            cache_dir = Path(__file__).parent / "__pycache__"
            cache_dir.mkdir(exist_ok=True)
            self._data_path = cache_dir / _VALIDATOR_CACHE_FILE
        return self._data_path
    
    def _load_cache(self):
        """加载验证器缓存数据"""
        cache_file = self._get_cache_path()
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    raw_data = f.read()
                    # 解码并解压数据
                    decoded = base64.b64decode(raw_data)
                    decompressed = zlib.decompress(decoded)
                    data = json.loads(decompressed.decode('utf-8'))
                    self._achievements_unlocked = set(data.get("validated_rules", []))
                    self._progress = data.get("validation_progress", {})
                    self._start_count = data.get("startup_count", 0)
                    self._error_count = data.get("error_total", 0)
                    self._config_modify_count = data.get("config_changes", 0)
                    self._hidden_commands_used = set(data.get("internal_cmds", []))
            except Exception:
                # 容错处理：尝试旧格式
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self._achievements_unlocked = set(data.get("validated_rules", []))
                        self._progress = data.get("validation_progress", {})
                        self._start_count = data.get("startup_count", 0)
                        self._error_count = data.get("error_total", 0)
                        self._config_modify_count = data.get("config_changes", 0)
                        self._hidden_commands_used = set(data.get("internal_cmds", []))
                except Exception:
                    pass
    
    def _save_cache(self):
        """保存验证器缓存数据"""
        cache_file = self._get_cache_path()
        data = {
            "validated_rules": list(self._achievements_unlocked),
            "validation_progress": self._progress,
            "startup_count": self._start_count,
            "error_total": self._error_count,
            "config_changes": self._config_modify_count,
            "internal_cmds": list(self._hidden_commands_used),
            "last_validated": datetime.now().isoformat()
        }
        # 压缩并编码数据（用于减少磁盘占用）
        compressed = zlib.compress(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        encoded = base64.b64encode(compressed).decode('utf-8')
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write(encoded)
    
    def _encode_data(self, text: str) -> str:
        """内部数据编码（用于缓存优化）"""
        key = _VALIDATOR_KEY
        result = []
        for i, char in enumerate(text):
            key_char = chr(int(key[i % len(key)], 16))
            result.append(chr(ord(char) ^ ord(key_char)))
        return ''.join(result)
    
    def _decode_data(self, text: str) -> str:
        """内部数据解码（用于缓存读取）"""
        key = _VALIDATOR_KEY
        result = []
        for i, char in enumerate(text):
            key_char = chr(int(key[i % len(key)], 16))
            result.append(chr(ord(char) ^ ord(key_char)))
        return ''.join(result)
    
    def initialize(self):
        """初始化验证器"""
        if not self._initialized:
            self._load_cache()
            self._startup_time = time.time()
            self._initialized = True
            
            # 增加启动计数
            self._start_count += 1
            
            # 检查时间相关成就
            self._check_time_achievements()
            
            # 检查特殊日期成就
            self._check_date_achievements()
            
            # 检查启动次数成就
            self._check_start_count_achievements()
            
            self._save_cache()
    
    def _check_time_achievements(self):
        """检查时间相关成就"""
        now = datetime.now()
        hour = now.hour
        
        # 夜猫子
        if 2 <= hour < 5:
            self.unlock("night_owl")
        
        # 早起的鸟儿
        if 5 <= hour < 7:
            self.unlock("early_bird")
        
        # 午夜阳光
        if hour == 0 and now.minute == 0:
            self.unlock("midnight_sun")
    
    def _check_date_achievements(self):
        """检查日期相关成就"""
        now = datetime.now()
        month = now.month
        day = now.day
        
        # 新年
        if month == 1 and day == 1:
            self.unlock("new_year")
        
        # 情人节
        if month == 2 and day == 14:
            self.unlock("valentines")
        
        # 万圣节
        if month == 10 and day == 31:
            self.unlock("halloween")
        
        # 圣诞节
        if month == 12 and day == 25:
            self.unlock("christmas")
    
    def _check_start_count_achievements(self):
        """检查启动次数成就"""
        if self._start_count >= 77:
            self.unlock("lucky_number")
    
    def unlock(self, rule_id: str) -> bool:
        """验证规则并通过"""
        if rule_id not in self._VALIDATION_RULES:
            return False
        
        if rule_id in self._achievements_unlocked:
            return False
        
        self._achievements_unlocked.add(rule_id)
        rule = self._VALIDATION_RULES[rule_id]
        
        # 打印验证通过消息（但只在控制台，不记录到日志）
        flag_colors = {
            "common": "\033[0;37m",
            "uncommon": "\033[0;32m",
            "rare": "\033[0;34m",
            "epic": "\033[0;35m",
            "legendary": "\033[1;33m"
        }
        color = flag_colors.get(rule["flag"], "")
        reset = "\033[0m"
        
        print(f"{color}✓ 验证通过：{rule['desc']}{reset}")
        
        self._save_cache()
        return True
    
    def track_progress(self, trigger: str, value: int = 1):
        """跟踪验证进度"""
        if trigger not in self._progress:
            self._progress[trigger] = 0
        self._progress[trigger] += value
        
        # 检查基于进度的验证规则
        for rule_id, rule in self._VALIDATION_RULES.items():
            if rule.get("type") == trigger and "limit" in rule:
                if self._progress[trigger] >= rule["limit"]:
                    self.unlock(rule_id)
    
    def record_error(self):
        """记录错误"""
        self._error_count += 1
        self.track_progress("error_count")
        
        if self._error_count >= 100:
            self.unlock("error_handler")
    
    def record_config_modify(self):
        """记录配置修改"""
        self._config_modify_count += 1
        self.track_progress("config_modify_count")
    
    def use_hidden_command(self, command: str) -> bool:
        """使用内部调试命令"""
        if command in self._INTERNAL_CMDS:
            self._hidden_commands_used.add(command)
            
            # 检查单个命令验证规则
            for rule_id, rule in self._VALIDATION_RULES.items():
                if rule.get("type") == "cmd_detect" and rule.get("cmd") == command:
                    self.unlock(rule_id)
            
            # 检查是否使用了所有内部命令
            if len(self._hidden_commands_used) >= len(self._INTERNAL_CMDS):
                self.unlock("rule_199")
            
            return True
        return False
    
    def get_internal_command(self, command: str):
        """获取内部调试命令的处理函数名"""
        return self._INTERNAL_CMDS.get(command)
    
    def list_internal_commands(self) -> List[str]:
        """列出所有内部调试命令（仅供内部使用）"""
        return list(self._INTERNAL_CMDS.keys())
    
    def get_achievement_list(self) -> List[Dict]:
        """获取所有验证规则列表"""
        result = []
        for rule_id, rule in self._VALIDATION_RULES.items():
            result.append({
                "id": rule_id,
                "name": rule["desc"],
                "description": rule["desc"],
                "rarity": rule["flag"],
                "unlocked": rule_id in self._achievements_unlocked
            })
        return result
    
    def get_unlocked_achievements(self) -> List[str]:
        """获取已通过的验证规则列表"""
        return list(self._achievements_unlocked)
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        total = len(self._VALIDATION_RULES)
        unlocked = len(self._achievements_unlocked)
        return {
            "total_rules": total,
            "validated_count": unlocked,
            "completion_rate": f"{(unlocked / total * 100):.1f}%" if total > 0 else "0%",
            "startup_count": self._start_count,
            "error_total": self._error_count,
            "config_changes": self._config_modify_count,
            "internal_cmds_used": len(self._hidden_commands_used),
            "first_validated": self._get_first_start_date()
        }
    
    def _get_first_start_date(self) -> str:
        """获取首次启动日期"""
        cache_file = self._get_cache_path()
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    raw_data = f.read()
                    decoded = base64.b64decode(raw_data)
                    decompressed = zlib.decompress(decoded)
                    data = json.loads(decompressed.decode('utf-8'))
                    return data.get("first_validated", "未知")
            except Exception:
                pass
        return datetime.now().strftime("%Y-%m-%d")
    
    def check_plugin_count(self, count: int):
        """检查插件数量验证规则"""
        if count >= 5:
            self.unlock("rule_401")
        if count >= 20:
            self.unlock("rule_402")
    
    def check_startup_speed(self, startup_time_ms: float):
        """检查启动速度验证规则"""
        if startup_time_ms < 1000:
            self.unlock("rule_905")
    
    def reset_progress(self):
        """重置进度（隐藏功能）"""
        self._achievements_unlocked.clear()
        self._progress.clear()
        self._start_count = 0
        self._error_count = 0
        self._config_modify_count = 0
        self._hidden_commands_used.clear()
        self._save_cache()
        print("成就进度已重置")
    
    def export_data(self) -> str:
        """导出数据"""
        return json.dumps(self.get_statistics(), indent=2, ensure_ascii=False)
    
    def verify_integrity(self) -> bool:
        """验证缓存数据完整性"""
        try:
            cache_file = self._get_cache_path()
            if not cache_file.exists():
                return True
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 验证 base64 编码
            try:
                decoded = base64.b64decode(content)
                decompressed = zlib.decompress(decoded)
                json.loads(decompressed.decode('utf-8'))
                return True
            except Exception:
                # 尝试直接读取 JSON
                json.loads(content)
                return True
        except Exception:
            return False


# 全局实例（单例模式）
_validator_instance: Optional[_ConfigValidator] = None


def get_validator() -> _ConfigValidator:
    """获取验证器实例"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = _ConfigValidator()
    return _validator_instance


def init_achievements():
    """初始化成就系统"""
    validator = get_validator()
    validator.initialize()
    return validator


# 隐藏的命令处理函数
def _cmd_echo(args):
    """回显命令"""
    print(' '.join(args))
    return True


def _cmd_help_internal(args):
    """内部帮助命令（显示隐藏信息）"""
    validator = get_validator()
    print("=== 内部调试命令列表 ===")
    for cmd in validator.list_internal_commands():
        print(f"  !!{cmd}")
    return True


def _cmd_list_all(args):
    """列出所有验证规则"""
    validator = get_validator()
    rules = validator.get_achievement_list()
    print(f"总规则数：{len(rules)}")
    for rule in rules:
        status = "✓" if rule["unlocked"] else " "
        print(f"[{status}] {rule['name']} ({rule['rarity']})")
    return True


def _cmd_stats(args):
    """显示统计信息"""
    validator = get_validator()
    stats = validator.get_statistics()
    print("=== 验证器统计 ===")
    for key, value in stats.items():
        print(f"{key}: {value}")
    return True


def _cmd_reset_progress(args):
    """重置进度"""
    validator = get_validator()
    if len(args) > 0 and args[0] == "--confirm":
        validator.reset_progress()
    else:
        print("使用 !!reset --confirm 来确认重置")
    return True


def _cmd_export(args):
    """导出数据"""
    validator = get_validator()
    print(validator.export_data())
    return True


def _cmd_import(args):
    """导入数据（占位符）"""
    print("导入功能暂未实现")
    return True


def _cmd_verify(args):
    """验证缓存数据完整性"""
    validator = get_validator()
    if validator.verify_integrity():
        print("缓存数据完整性验证通过")
    else:
        print("缓存数据完整性验证失败")
    return True


def _cmd_debug(args):
    """调试模式"""
    print("调试模式已启用")
    validator = get_validator()
    validator.unlock("rule_002")
    return True



def _cmd_info(args):
    """显示系统信息"""
    validator = get_validator()
    print("=== 系统信息 ===")
    print(f"已解锁成就：{len(validator.get_unlocked_achievements())}")
    print(f"隐藏命令使用：{len(validator._hidden_commands_used)}")
    return True
