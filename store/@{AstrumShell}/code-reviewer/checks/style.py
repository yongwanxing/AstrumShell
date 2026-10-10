"""风格检查器"""


class StyleChecker:
    """风格检查器"""

    def check(self, filepath: str, content: str) -> list:
        """执行风格检查"""
        issues = []

        # 检查行长度
        issues.extend(self._check_line_length(filepath, content))

        # 检查空行
        issues.extend(self._check_blank_lines(filepath, content))

        # 检查文件末尾换行
        issues.extend(self._check_final_newline(filepath, content))

        return issues

    def _check_line_length(self, filepath: str, content: str) -> list:
        """检查行长度"""
        issues = []

        for i, line in enumerate(content.split('\n'), 1):
            if len(line) > 120:
                issues.append({
                    "file": filepath,
                    "line": i,
                    "severity": "info",
                    "type": "line_too_long",
                    "message": f"行过长 ({len(line)} 字符)"
                })

        return issues

    def _check_blank_lines(self, filepath: str, content: str) -> list:
        """检查连续空行"""
        issues = []
        blank_count = 0

        for i, line in enumerate(content.split('\n'), 1):
            if line.strip() == '':
                blank_count += 1
                if blank_count > 2:
                    issues.append({
                        "file": filepath,
                        "line": i,
                        "severity": "info",
                        "type": "too_many_blanks",
                        "message": "连续空行过多"
                    })
            else:
                blank_count = 0

        return issues

    def _check_final_newline(self, filepath: str, content: str) -> list:
        """检查文件末尾换行"""
        if content and not content.endswith('\n'):
            return [{
                "file": filepath,
                "line": len(content.split('\n')),
                "severity": "info",
                "type": "missing_final_newline",
                "message": "文件末尾缺少换行符"
            }]

        return []
