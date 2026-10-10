"""引用检查器 - 检测导入错误、变量错误等"""
import ast
import sys
import os
from pathlib import Path


class ReferenceChecker:
    """引用检查器"""

    # Python 标准库模块列表
    STD_MODULES = {
        'os', 'sys', 'json', 're', 'time', 'datetime', 'pathlib',
        'typing', 'collections', 'functools', 'itertools', 'io',
        'string', 'math', 'random', 'hashlib', 'hmac', 'secrets',
        'urllib', 'http', 'email', 'html', 'xml', 'csv', 'configparser',
        'logging', 'warnings', 'traceback', 'inspect', 'importlib',
        'threading', 'multiprocessing', 'subprocess', 'socket',
        'asyncio', 'concurrent', 'queue', 'contextlib', 'abc',
        'enum', 'dataclasses', 'copy', 'pprint', 'textwrap',
        'struct', 'codecs', 'locale', 'gettext', 'argparse',
        'unittest', 'doctest', 'pdb', 'profile', 'timeit',
        'tempfile', 'glob', 'fnmatch', 'stat', 'fileinput',
        'shutil', 'pickle', 'shelve', 'sqlite3', 'dbm',
        'gzip', 'bz2', 'lzma', 'zipfile', 'tarfile',
        'base64', 'binascii', 'quopri', 'uu',
    }

    # Python 内置函数和类型（不应报告为未定义）
    BUILTINS = {
        'print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict',
        'set', 'tuple', 'range', 'enumerate', 'zip', 'map', 'filter',
        'sorted', 'reversed', 'min', 'max', 'sum', 'abs', 'round',
        'isinstance', 'issubclass', 'type', 'id', 'hash', 'repr',
        'True', 'False', 'None', 'Exception', 'ValueError', 'TypeError',
        'KeyError', 'AttributeError', 'ImportError', 'FileNotFoundError',
        'IndexError', 'RuntimeError', 'StopIteration', 'GeneratorExit',
        'staticmethod', 'classmethod', 'property', 'super',
        'open', 'input', 'format', 'hex', 'oct', 'bin', 'chr', 'ord',
        'dir', 'vars', 'locals', 'globals', 'callable', 'getattr',
        'setattr', 'hasattr', 'delattr', 'exec', 'eval', 'compile',
        'any', 'all', 'slice', 'frozenset', 'bytearray', 'bytes',
        'memoryview', 'complex', 'divmod', 'pow', 'object',
        'dict', 'list', 'str', 'int', 'float', 'bool', 'set',
        'tuple', 'Exception', 'ValueError', 'TypeError', 'KeyError',
        'self', 'cls', 'args', 'kwargs',
    }

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self._available_modules = set(self.STD_MODULES)
        self._scan_project_modules()

    def _scan_project_modules(self):
        """扫描项目中的可用模块"""
        # 扫描 oss 目录（框架核心）
        oss_dir = self.project_root / "oss"
        if oss_dir.exists():
            self._available_modules.add("oss")
            self._scan_module_dir(oss_dir, "oss")

        # 扫描 store 目录下的所有插件
        store_dir = self.project_root / "store"
        if store_dir.exists():
            for author_dir in store_dir.iterdir():
                if not author_dir.is_dir():
                    continue
                for plugin_dir in author_dir.iterdir():
                    if not plugin_dir.is_dir():
                        continue
                    plugin_name = plugin_dir.name
                    # 添加插件名作为可用模块
                    self._available_modules.add(plugin_name)
                    # 扫描插件内部的子模块
                    self._scan_plugin_modules(plugin_dir, plugin_name)

    def _scan_module_dir(self, dir_path: Path, base_name: str):
        """扫描模块目录"""
        if dir_path.exists():
            for item in dir_path.iterdir():
                if item.is_file() and item.name.endswith(".py") and item.name != "__init__.py":
                    module_name = item.name[:-3]
                    full_name = f"{base_name}.{module_name}"
                    self._available_modules.add(full_name)
                elif item.is_dir() and (item / "__init__.py").exists():
                    full_name = f"{base_name}.{item.name}"
                    self._available_modules.add(full_name)
                    self._scan_module_dir(item, full_name)

    def _scan_plugin_modules(self, plugin_dir: Path, base_name: str):
        """扫描插件内部的子模块"""
        for item in plugin_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                full_name = f"{base_name}.{item.name}"
                self._available_modules.add(full_name)
                self._scan_module_dir(item, full_name)
            elif item.is_file() and item.name.endswith(".py") and item.name != "__init__.py":
                module_name = item.name[:-3]
                full_name = f"{base_name}.{module_name}"
                self._available_modules.add(full_name)

    def _add_module_from_dir(self, dir_path: Path, base_name: str):
        """从目录添加模块"""
        if dir_path.exists():
            for item in dir_path.iterdir():
                if item.is_file() and item.name.endswith(".py") and item.name != "__init__.py":
                    module_name = item.name[:-3]
                    self._available_modules.add(f"{base_name}.{module_name}")
                elif item.is_dir() and (item / "__init__.py").exists():
                    self._add_module_from_dir(item, f"{base_name}.{item.name}")

    def check(self, filepath: str, content: str) -> list:
        """执行引用检查"""
        issues = []

        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return [{
                "file": filepath,
                "line": e.lineno or 0,
                "severity": "critical",
                "type": "syntax_error",
                "message": f"语法错误: {e.msg}"
            }]

        # 检查导入语句（跳过相对导入）
        issues.extend(self._check_imports(filepath, tree))

        # 检查属性访问错误
        issues.extend(self._check_attribute_access(filepath, tree, content))

        # 检查函数调用错误
        issues.extend(self._check_function_calls(filepath, tree, content))

        return issues

    def _check_imports(self, filepath: str, tree: ast.AST) -> list:
        """检查导入语句"""
        issues = []
        file_path = Path(filepath)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # 跳过 oss 框架模块（运行时可用）
                    if alias.name.startswith('oss.') or alias.name == 'oss':
                        continue
                    # 跳过 websockets 等第三方库
                    if alias.name in ('websockets', 'yaml', 'click'):
                        continue
                    if not self._is_module_available(alias.name, file_path):
                        issues.append({
                            "file": filepath,
                            "line": node.lineno,
                            "severity": "critical",
                            "type": "import_error",
                            "message": f"无法导入模块: {alias.name}"
                        })

            elif isinstance(node, ast.ImportFrom):
                # 跳过相对导入（以 . 开头）
                if node.level and node.level > 0:
                    continue

                # 跳过 oss 框架模块
                if node.module and (node.module.startswith('oss.') or node.module == 'oss'):
                    continue

                # 跳过第三方库
                if node.module and node.module.split('.')[0] in ('websockets', 'yaml', 'click'):
                    continue

                if node.module:
                    if not self._is_module_available(node.module, file_path):
                        issues.append({
                            "file": filepath,
                            "line": node.lineno,
                            "severity": "critical",
                            "type": "import_error",
                            "message": f"无法导入模块: {node.module}"
                        })

        return issues

    def _check_variable_references(self, filepath: str, tree: ast.AST, content: str) -> list:
        """检查变量引用"""
        issues = []
        lines = content.split('\n')

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                # 检查是否引用了未定义的变量
                if not self._is_name_defined(node.id, tree, node.lineno):
                    if node.id not in ('True', 'False', 'None', 'self', 'cls'):
                        issues.append({
                            "file": filepath,
                            "line": node.lineno,
                            "severity": "warning",
                            "type": "undefined_variable",
                            "message": f"使用了未定义的变量: {node.id}"
                        })

        return issues

    def _check_attribute_access(self, filepath: str, tree: ast.AST, content: str) -> list:
        """检查属性访问"""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                # 检查可能的属性错误
                if isinstance(node.value, ast.Name):
                    var_name = node.value.id
                    if var_name in ('None', 'True', 'False'):
                        issues.append({
                            "file": filepath,
                            "line": node.lineno,
                            "severity": "critical",
                            "type": "attribute_error",
                            "message": f"尝试访问 {var_name} 的属性: {node.attr}"
                        })

        return issues

    def _check_function_calls(self, filepath: str, tree: ast.AST, content: str) -> list:
        """检查函数调用"""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # 检查调用不存在的方法
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Constant) and node.func.value.value is None:
                        issues.append({
                            "file": filepath,
                            "line": node.lineno,
                            "severity": "critical",
                            "type": "method_call_on_none",
                            "message": f"在 None 上调用方法: {node.func.attr}"
                        })

        return issues

    def _is_module_available(self, module_name: str, file_path: Path = None) -> bool:
        """检查模块是否可用"""
        # 检查是否在已扫描的模块中
        if module_name in self._available_modules:
            return True

        # 检查标准库
        base_module = module_name.split('.')[0]
        if base_module in self.STD_MODULES:
            return True

        # 检查是否是 oss 框架模块
        if module_name.startswith('oss.') or module_name == 'oss':
            return True

        # 检查是否是常见第三方库
        third_party = {'websockets', 'yaml', 'click', 'requests', 'flask', 'django', 'numpy', 'pandas'}
        if module_name.split('.')[0] in third_party:
            return True

        # 检查是否是当前文件的同目录模块（相对导入的情况）
        if file_path:
            file_dir = file_path.parent
            # 检查同级 .py 文件
            sibling_module = file_dir / f"{module_name}.py"
            if sibling_module.exists():
                return True
            # 检查同级包
            sibling_pkg = file_dir / module_name
            if sibling_pkg.is_dir() and (sibling_pkg / "__init__.py").exists():
                return True
            # 检查 store 目录下的插件
            store_dir = self.project_root / "store"
            if store_dir.exists():
                for author_dir in store_dir.iterdir():
                    if author_dir.is_dir():
                        for plugin_dir in author_dir.iterdir():
                            if plugin_dir.is_dir() and plugin_dir.name == module_name.split('.')[0]:
                                return True

        return False

    def _is_name_defined(self, name: str, tree: ast.AST, line: int) -> bool:
        """检查名称是否已定义"""
        # 检查是否是内置函数/类型
        if name in self.BUILTINS:
            return True

        # 检查是否是函数参数
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for arg in node.args.args:
                    if arg.arg == name:
                        return True

            # 检查是否是赋值目标
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == name:
                        return True

            # 检查是否是循环变量
            elif isinstance(node, ast.For):
                if isinstance(node.target, ast.Name) and node.target.id == name:
                    return True

            # 检查是否是导入
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname == name or alias.name == name:
                        return True

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for alias in node.names:
                        if alias.asname == name or alias.name == name:
                            return True

        return False
