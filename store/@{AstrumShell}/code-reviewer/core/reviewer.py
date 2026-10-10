"""代码审查器核心"""
import os
import ast
import json
import time
from pathlib import Path
from typing import Any
from checks.security import SecurityChecker
from checks.quality import QualityChecker
from checks.style import StyleChecker
from checks.references import ReferenceChecker
from report.formatter import ReportFormatter


class CodeReviewer:
    """代码审查器"""

    def __init__(self, config: dict):
        self.config = config
        self.security = SecurityChecker()
        self.quality = QualityChecker()
        self.style = StyleChecker()
        self.references = ReferenceChecker()
        self.formatter = ReportFormatter(config.get("report_format", "console"))

    def run_check(self, scan_dirs: list) -> dict:
        """执行检查"""
        start_time = time.time()
        issues = []
        files_scanned = 0

        for scan_dir in scan_dirs:
            if not os.path.exists(scan_dir):
                continue

            for root, dirs, files in os.walk(scan_dir):
                # 排除目录
                dirs[:] = [d for d in dirs if d not in self.config.get("exclude_patterns", [])]

                for file in files:
                    if file.endswith('.py'):
                        filepath = os.path.join(root, file)
                        file_size = os.path.getsize(filepath)

                        if file_size > self.config.get("max_file_size", 102400):
                            continue

                        issues.extend(self._check_file(filepath))
                        files_scanned += 1

        elapsed = time.time() - start_time

        result = {
            "status": "completed",
            "files_scanned": files_scanned,
            "total_issues": len(issues),
            "issues": issues,
            "scan_time": round(elapsed, 2),
            "timestamp": time.time()
        }

        print(self.formatter.format(result))
        return result

    def _check_file(self, filepath: str) -> list:
        """检查单个文件"""
        issues = []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # 安全检查
            issues.extend(self.security.check(filepath, content))

            # 质量检查
            issues.extend(self.quality.check(filepath, content))

            # 风格检查
            issues.extend(self.style.check(filepath, content))

            # 引用检查（新增）
            issues.extend(self.references.check(filepath, content))

        except Exception as e:
            issues.append({
                "file": filepath,
                "line": 0,
                "severity": "error",
                "type": "parse_error",
                "message": f"文件解析失败: {e}"
            })

        return issues
