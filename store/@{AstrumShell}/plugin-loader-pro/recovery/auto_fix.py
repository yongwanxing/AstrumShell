"""自动修复器"""
import time
import importlib
import sys
from pathlib import Path
from ..utils.logger import ProLogger


class AutoRecovery:
    """自动修复器"""

    def __init__(self, max_attempts: int = 3, delay: int = 10):
        self.max_attempts = max_attempts
        self.delay = delay
        self._recovery_attempts: dict[str, int] = {}

    def attempt_recovery(self, name: str, plugin_dir: Path,
                         module: any, instance: any) -> bool:
        """尝试恢复插件"""
        attempts = self._recovery_attempts.get(name, 0)

        if attempts >= self.max_attempts:
            ProLogger.error("recovery", f"插件 {name} 已达到最大恢复次数，放弃恢复")
            return False

        ProLogger.warn("recovery", f"尝试恢复插件 {name} (第 {attempts + 1} 次)")

        try:
            time.sleep(self.delay)

            # 重新加载模块
            if module and hasattr(module, '__file__'):
                module_path = Path(module.__file__)
                if module_path.exists():
                    spec = importlib.util.spec_from_file_location(
                        module.__name__, str(module_path)
                    )
                    new_module = importlib.util.module_from_spec(spec)
                    sys.modules[spec.name] = new_module
                    spec.loader.exec_module(new_module)

                    if hasattr(new_module, 'New'):
                        new_instance = new_module.New()
                        ProLogger.info("recovery", f"插件 {name} 恢复成功")
                        self._recovery_attempts[name] = 0
                        return new_instance

        except Exception as e:
            ProLogger.error("recovery", f"恢复插件 {name} 失败: {type(e).__name__}: {e}")

        self._recovery_attempts[name] = attempts + 1
        return False

    def reset_attempts(self, name: str):
        """重置恢复尝试次数"""
        self._recovery_attempts[name] = 0

    def get_attempts(self, name: str) -> int:
        """获取恢复尝试次数"""
        return self._recovery_attempts.get(name, 0)
