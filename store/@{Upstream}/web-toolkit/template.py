"""模板引擎"""
import re
import ast
from pathlib import Path
from typing import Any, Optional


class TemplateEngine:
    """简单模板引擎"""

    def __init__(self, root: str = "./templates", max_depth: int = 10):
        self.root = root
        self._cache: dict[str, str] = {}
        self.max_depth = max_depth
        self._ensure_root()

    def _ensure_root(self):
        """确保模板目录存在"""
        Path(self.root).mkdir(parents=True, exist_ok=True)

    def set_root(self, path: str):
        """设置模板根目录"""
        self.root = path
        self._ensure_root()
        self._cache.clear()

    def render(self, name: str, context: dict[str, Any]) -> str:
        """渲染模板"""
        template = self._load_template(name)
        return self._render_template(template, context, depth=0)

    def _load_template(self, name: str) -> str:
        """加载模板"""
        if name in self._cache:
            return self._cache[name]

        template_path = Path(self.root) / name
        if not template_path.exists():
            raise FileNotFoundError(f"模板不存在: {name}")

        content = template_path.read_text(encoding="utf-8")
        self._cache[name] = content
        return content

    def _safe_eval(self, expression: str, context: dict) -> Any:
        """安全评估表达式（使用 AST 验证，不使用 eval）"""
        try:
            tree = ast.parse(expression, mode='eval')
        except SyntaxError:
            return False

        # 验证 AST 节点
        if not self._validate_ast(tree.body[0].value, set(context.keys())):
            return False

        # 使用安全的 AST 解释器，不使用 eval
        try:
            return self._eval_ast(tree.body[0].value, context)
        except Exception:
            return False

    def _eval_ast(self, node: ast.AST, context: dict) -> Any:
        """安全地评估 AST 节点"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return context.get(node.id, False)
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                return all(self._eval_ast(v, context) for v in node.values)
            elif isinstance(node.op, ast.Or):
                return any(self._eval_ast(v, context) for v in node.values)
        elif isinstance(node, ast.Compare):
            return self._eval_compare(node, context)
        elif isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return not self._eval_ast(node.operand, context)
        elif isinstance(node, ast.Subscript):
            return self._eval_subscript(node, context)
        return False

    def _eval_compare(self, node: ast.Compare, context: dict) -> bool:
        """评估比较表达式"""
        left = self._eval_ast(node.left, context)
        for op, comp in zip(node.ops, node.comparators):
            right = self._eval_ast(comp, context)
            if isinstance(op, ast.Eq):
                if not (left == right): return False
            elif isinstance(op, ast.NotEq):
                if not (left != right): return False
            elif isinstance(op, ast.Lt):
                if not (left < right): return False
            elif isinstance(op, ast.Gt):
                if not (left > right): return False
            elif isinstance(op, ast.LtE):
                if not (left <= right): return False
            elif isinstance(op, ast.GtE):
                if not (left >= right): return False
            elif isinstance(op, ast.In):
                if not (left in right): return False
            elif isinstance(op, ast.NotIn):
                if not (left not in right): return False
            left = right
        return True

    def _eval_subscript(self, node: ast.Subscript, context: dict) -> Any:
        """评估下标访问"""
        value = self._eval_ast(node.value, context)
        key = self._eval_ast(node.slice, context)
        if isinstance(value, (dict, list, str)):
            return value[key]
        return None

    def _validate_ast(self, node: ast.AST, allowed_names: set) -> bool:
        """验证 AST 只包含安全的操作"""
        if isinstance(node, ast.Name):
            return node.id in allowed_names or node.id in ('True', 'False', 'None')
        elif isinstance(node, ast.Constant):
            return True
        elif isinstance(node, ast.BoolOp):
            return all(self._validate_ast(v, allowed_names) for v in node.values)
        elif isinstance(node, ast.Compare):
            return (self._validate_ast(node.left, allowed_names) and 
                    all(self._validate_ast(c, allowed_names) for c in node.comparators))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return self._validate_ast(node.operand, allowed_names)
        elif isinstance(node, ast.Attribute):
            # 不允许属性访问（防止绕过安全限制）
            return False
        elif isinstance(node, ast.Call):
            # 不允许函数调用
            return False
        elif isinstance(node, ast.Subscript):
            # 允许简单的索引访问
            return (self._validate_ast(node.value, allowed_names) and 
                    self._validate_ast(node.slice, allowed_names))
        return False

    def _render_template(self, template: str, context: dict[str, Any], depth: int = 0) -> str:
        """渲染模板内容
        
        Args:
            template: 模板内容
            context: 上下文变量
            depth: 当前递归深度
        
        Raises:
            RecursionError: 当嵌套深度超过 max_depth 时
        """
        if depth > self.max_depth:
            raise RecursionError(
                f"模板嵌套深度超过限制 ({self.max_depth})，可能存在无限递归"
            )
        
        # 替换 {{ variable }}
        def replace_var(match):
            var_name = match.group(1).strip()
            value = context.get(var_name, "")
            if isinstance(value, (dict, list)):
                import json
                return json.dumps(value, ensure_ascii=False)
            return str(value)

        result = re.sub(r'\{\{(.*?)\}\}', replace_var, template)

        # 处理 {% if condition %} ... {% endif %}
        result = self._process_if(result, context, depth)

        # 处理 {% for item in list %} ... {% endfor %}
        result = self._process_for(result, context, depth)

        return result

    def _process_if(self, template: str, context: dict, depth: int = 0) -> str:
        """处理 if 条件"""
        pattern = r'\{%\s*if\s+(.*?)\s*%\}(.*?){%\s*endif\s*%\}'

        def replace_if(match):
            condition = match.group(1).strip()
            content = match.group(2)
            # 安全条件评估
            value = self._safe_eval(condition, context)
            if value:
                # 递归处理嵌套内容，深度+1
                return self._render_template(content, context, depth + 1)
            return ""

        return re.sub(pattern, replace_if, template, flags=re.DOTALL)

    def _process_for(self, template: str, context: dict, depth: int = 0) -> str:
        """处理 for 循环"""
        pattern = r'\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?){%\s*endfor\s*%\}'

        def replace_for(match):
            item_name = match.group(1)
            list_name = match.group(2)
            content = match.group(3)

            items = context.get(list_name, [])
            if not isinstance(items, list):
                return ""

            result = ""
            for item in items:
                loop_context = {**context, item_name: item}
                # 递归处理嵌套内容，深度+1
                result += self._render_template(content, loop_context, depth + 1)
            return result

        return re.sub(pattern, replace_for, template, flags=re.DOTALL)
