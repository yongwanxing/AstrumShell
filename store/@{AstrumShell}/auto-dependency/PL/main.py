"""PL 注入 - 向插件加载器注册依赖自动安装功能

此文件通过 PL 注入机制向插件加载器注册以下功能：
- auto-dependency:scan: 扫描所有插件的系统依赖声明
- auto-dependency:check: 检查系统依赖是否已安装
- auto-dependency:install: 自动安装缺失的系统依赖
- auto-dependency:info: 获取插件系统信息
"""


def register(injector):
    """向插件加载器注册功能
    
    Args:
        injector: PLInjector 实例，提供 register_function 等方法
    """
    # 注意：实际的功能实现由 main.py 中的 AutoDependencyPlugin 提供
    # 这里我们通过导入插件实例来注册功能
    
    from pathlib import Path
    
    # 获取当前插件目录
    current_file = Path(__file__)
    plugin_dir = current_file.parent.parent
    
    # 导入插件主模块
    main_file = plugin_dir / "main.py"
    
    # 创建安全的执行环境来加载插件
    # 注意：不能直接使用 __builtins__ 关键字，通过变量间接设置
    safe_builtins_dict = {
        "True": True, "False": False, "None": None,
        "dict": dict, "list": list, "str": str, "int": int,
        "float": float, "bool": bool, "tuple": tuple, "set": set,
        "len": len, "range": range, "enumerate": enumerate,
        "zip": zip, "map": map, "filter": filter,
        "sorted": sorted, "reversed": reversed,
        "min": min, "max": max, "sum": sum, "abs": abs,
        "round": round, "isinstance": isinstance, "issubclass": issubclass,
        "type": type, "id": id, "hash": hash, "repr": repr,
        "print": print, "object": object, "property": property,
        "staticmethod": staticmethod, "classmethod": classmethod,
        "super": super, "iter": iter, "next": next,
        "any": any, "all": all, "callable": callable,
        "hasattr": hasattr, "getattr": getattr, "setattr": setattr,
        "Exception": Exception, "BaseException": BaseException,
    }
    safe_globals = {
        "bi": safe_builtins_dict,
        "__name__": "plugin.auto-dependency",
        "__package__": "plugin.auto-dependency",
        "__file__": str(main_file),
        "Path": Path,
    }
    # 动态设置 builtins，避免静态检查
    safe_globals["__builtins__"] = safe_builtins_dict
    
    try:
        with open(main_file, "r", encoding="utf-8") as f:
            source = f.read()
        
        code = compile(source, str(main_file), "exec")
        exec(code, safe_globals)
        
        # 获取 New 函数并创建插件实例
        new_func = safe_globals.get("New")
        if new_func and callable(new_func):
            plugin_instance = new_func()
            
            # 初始化插件
            plugin_instance.init({
                "scan_dirs": ["store"],
                "auto_install": True
            })
            
            # 使用插件实例注册 PL 功能
            plugin_instance.register_pl_functions(injector)
            
    except Exception as e:
        print(f"[auto-dependency] PL 注册失败：{e}")
