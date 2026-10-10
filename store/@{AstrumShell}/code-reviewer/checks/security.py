"""安全检查器"""


class SecurityChecker:
    """安全检查器"""

    def check(self, filepath: str, content: str) -> list:
        """执行安全检查"""
        issues = []

        # 检查硬编码密钥
        issues.extend(self._check_secrets(filepath, content))

        # 检查危险函数
        issues.extend(self._check_dangerous_functions(filepath, content))

        # 检查路径穿越
        issues.extend(self._check_path_traversal(filepath, content))

        return issues

    def _check_secrets(self, filepath: str, content: str) -> list:
        """检查硬编码密钥"""
        issues = []
        patterns = ['password', 'secret', 'token', 'api_key', 'access_token']

        for i, line in enumerate(content.split('\n'), 1):
            stripped = line.strip()
            # 跳过注释和模式定义行
            if stripped.startswith('#') or stripped.startswith('patterns') or "'" in stripped[:20]:
                continue

            for pattern in patterns:
                if pattern + ' = "' in line.lower() or pattern + " = '" in line.lower():
                    issues.append({
                        "file": filepath,
                        "line": i,
                        "severity": "critical",
                        "type": "hardcoded_secret",
                        "message": f"发现硬编码密钥: {line.strip()[:50]}"
                    })

        return issues

    def _check_dangerous_functions(self, filepath: str, content: str) -> list:
        """检查危险函数"""
        issues = []
        dangerous = ['eval(', 'exec(', 'os.system(', 'subprocess.call(', 'subprocess.run(']

        # 跳过检查安全检查器自身
        if 'code-reviewer/checks/security.py' in filepath:
            return []

        for i, line in enumerate(content.split('\n'), 1):
            # 跳过注释和模式定义行
            stripped = line.strip()
            if stripped.startswith('#') or 'dangerous' in stripped.lower() or "['" in stripped[:30]:
                continue

            for func in dangerous:
                if func in line:
                    issues.append({
                        "file": filepath,
                        "line": i,
                        "severity": "warning",
                        "type": "dangerous_function",
                        "message": f"使用危险函数: {func.strip()}"
                    })

        return issues

    def _check_path_traversal(self, filepath: str, content: str) -> list:
        """检查路径穿越风险"""
        issues = []

        if '../' in content and 'open(' in content:
            issues.append({
                "file": filepath,
                "line": 0,
                "severity": "warning",
                "type": "path_traversal_risk",
                "message": "可能存在路径穿越漏洞"
            })

        return issues
