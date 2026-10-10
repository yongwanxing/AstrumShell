"""质量检查器"""
import ast


class QualityChecker:
    """质量检查器"""

    def check(self, filepath: str, content: str) -> list:
        """执行质量检查"""
        issues = []

        # 检查函数长度
        issues.extend(self._check_function_length(filepath, content))

        # 检查参数数量
        issues.extend(self._check_parameter_count(filepath, content))

        # 检查复杂度
        issues.extend(self._check_complexity(filepath, content))

        return issues

    def _check_function_length(self, filepath: str, content: str) -> list:
        """检查函数长度"""
        issues = []

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    lines = node.end_lineno - node.lineno
                    if lines > 100:
                        issues.append({
                            "file": filepath,
                            "line": node.lineno,
                            "severity": "warning",
                            "type": "long_function",
                            "message": f"函数 {node.name} 过长 ({lines} 行)"
                        })
        except:
            pass

        return issues

    def _check_parameter_count(self, filepath: str, content: str) -> list:
        """检查参数数量"""
        issues = []

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    args = node.args
                    count = len(args.args)
                    if count > 5:
                        issues.append({
                            "file": filepath,
                            "line": node.lineno,
                            "severity": "info",
                            "type": "too_many_params",
                            "message": f"函数 {node.name} 参数过多 ({count} 个)"
                        })
        except:
            pass

        return issues

    def _check_complexity(self, filepath: str, content: str) -> list:
        """检查圈复杂度"""
        issues = []

        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    complexity = self._calculate_complexity(node)
                    if complexity > 10:
                        issues.append({
                            "file": filepath,
                            "line": node.lineno,
                            "severity": "warning",
                            "type": "high_complexity",
                            "message": f"函数 {node.name} 复杂度过高 (圈复杂度: {complexity})"
                        })
        except:
            pass

        return issues

    def _calculate_complexity(self, node: ast.AST) -> int:
        """计算圈复杂度"""
        complexity = 1

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return complexity
