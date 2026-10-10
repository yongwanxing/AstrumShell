"""依赖自动安装插件 - 扫描所有插件的声明文件，检查并安装系统依赖

功能说明：
1. 扫描所有插件目录下的 manifest.json 文件
2. 读取每个插件声明的系统依赖 (system_dependencies 字段)
3. 检查这些系统依赖是否已安装
4. 对于未安装的依赖，使用系统包管理器自动安装
5. 通过 PL 注入机制向插件加载器注册功能接口
"""
import subprocess
import shutil
import json
from pathlib import Path
from typing import Any, Optional, List, Dict
from oss.plugin.types import Plugin


class SystemDependencyChecker:
    """系统依赖检查器"""
    
    def __init__(self):
        self.package_managers = {
            "apt": ["apt-get", "apt"],
            "yum": ["yum", "dnf"],
            "pacman": ["pacman"],
            "brew": ["brew"],
            "apk": ["apk"],
            # Windows 包管理器（放在后面：POSIX 下优先用系统原生管理器）
            "winget": ["winget"],
            "choco": ["choco"],
            "scoop": ["scoop"],
        }
        self.detected_pm = self._detect_package_manager()
    
    def _detect_package_manager(self) -> str:
        """检测系统包管理器"""
        for pm, commands in self.package_managers.items():
            for cmd in commands:
                if shutil.which(cmd):
                    return pm
        return "unknown"
    
    def check_command(self, command: str) -> bool:
        """检查命令是否可用"""
        return shutil.which(command) is not None
    
    def check_package(self, package: str) -> bool:
        """检查系统包是否已安装"""
        # 通用且跨平台的判断：多数声明的系统依赖本身就是可执行命令（ffmpeg/nginx/git...），
        # 先用 PATH 查找，避免在没有受支持包管理器的平台（如 Windows 无 winget）上直接判为未安装
        if self.check_command(package):
            return True
        if not self.detected_pm or self.detected_pm == "unknown":
            return False
        
        try:
            if self.detected_pm in ["apt", "apt-get"]:
                result = subprocess.run(
                    ["dpkg", "-l", package],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.returncode == 0 and "ii" in result.stdout
            elif self.detected_pm in ["yum", "dnf"]:
                result = subprocess.run(
                    ["rpm", "-q", package],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.returncode == 0
            elif self.detected_pm == "pacman":
                result = subprocess.run(
                    ["pacman", "-Q", package],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.returncode == 0
            elif self.detected_pm == "brew":
                result = subprocess.run(
                    ["brew", "list", package],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.returncode == 0
            elif self.detected_pm == "apk":
                result = subprocess.run(
                    ["apk", "info", "-e", package],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.returncode == 0
            elif self.detected_pm == "winget":
                result = subprocess.run(
                    ["winget", "list", "--id", package, "--accept-source-agreements", "--disable-interactivity"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60
                )
                return result.returncode == 0 and package.lower() in (result.stdout or "").lower()
            elif self.detected_pm == "choco":
                result = subprocess.run(
                    ["choco", "list", "--local-only", package],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                return result.returncode == 0 and package.lower() in (result.stdout or "").lower()
            elif self.detected_pm == "scoop":
                result = subprocess.run(
                    ["scoop", "list", package],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                return result.returncode == 0
        except Exception as e:
            import traceback; print(f"[main.py] 错误:{type(e).__name__}:{e}"); traceback.print_exc()
            pass
        return False
    
    def install_package(self, package: str) -> bool:
        """安装系统包"""
        if not self.detected_pm or self.detected_pm == "unknown":
            return False
        
        try:
            if self.detected_pm in ["apt", "apt-get"]:
                result = subprocess.run(
                    ["apt-get", "install", "-y", package],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                return result.returncode == 0
            elif self.detected_pm == "yum":
                result = subprocess.run(
                    ["yum", "install", "-y", package],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                return result.returncode == 0
            elif self.detected_pm == "dnf":
                result = subprocess.run(
                    ["dnf", "install", "-y", package],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                return result.returncode == 0
            elif self.detected_pm == "pacman":
                result = subprocess.run(
                    ["pacman", "-S", "--noconfirm", package],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                return result.returncode == 0
            elif self.detected_pm == "brew":
                result = subprocess.run(
                    ["brew", "install", package],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                return result.returncode == 0
            elif self.detected_pm == "apk":
                result = subprocess.run(
                    ["apk", "add", package],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                return result.returncode == 0
            elif self.detected_pm == "winget":
                result = subprocess.run(
                    ["winget", "install", "--id", package, "--accept-package-agreements",
                     "--accept-source-agreements", "--disable-interactivity"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=900
                )
                return result.returncode == 0
            elif self.detected_pm == "choco":
                result = subprocess.run(
                    ["choco", "install", package, "-y"],
                    capture_output=True,
                    text=True,
                    timeout=900
                )
                return result.returncode == 0
            elif self.detected_pm == "scoop":
                result = subprocess.run(
                    ["scoop", "install", package],
                    capture_output=True,
                    text=True,
                    timeout=900
                )
                return result.returncode == 0
        except Exception as e:
            import traceback; print(f"[main.py] 错误:{type(e).__name__}:{e}"); traceback.print_exc()
            pass
        return False
    
    def check_and_install(self, package: str, auto_install: bool = True) -> Dict[str, Any]:
        """检查并安装包"""
        result = {
            "package": package,
            "installed": self.check_package(package),
            "action": "none",
            "success": True,
            "message": ""
        }
        
        if result["installed"]:
            result["message"] = f"包 '{package}' 已安装"
            return result
        
        if not auto_install:
            result["action"] = "skipped"
            result["message"] = f"包 '{package}' 未安装，但自动安装已禁用"
            result["success"] = False
            return result
        
        result["action"] = "installing"
        if self.install_package(package):
            result["installed"] = True
            result["success"] = True
            result["message"] = f"包 '{package}' 安装成功"
        else:
            result["success"] = False
            result["message"] = f"包 '{package}' 安装失败"
        
        return result


class AutoDependencyPlugin(Plugin):
    """依赖自动安装插件"""
    
    def __init__(self):
        self.checker = SystemDependencyChecker()
        self.scan_dirs: List[str] = []
        self.auto_install: bool = True
        self._plugin_loader_ref: Optional[Any] = None
    
    def init(self, deps: Optional[Dict[str, Any]] = None):
        """初始化插件"""
        if deps:
            self.scan_dirs = deps.get("scan_dirs", ["store"])
            self.auto_install = deps.get("auto_install", True)
            
            # 获取插件加载器引用（通过依赖注入）
            if "plugin-loader" in deps:
                self._plugin_loader_ref = deps["plugin-loader"]
    
    def start(self):
        """启动插件"""
        pass
    
    def stop(self):
        """停止插件"""
        pass
    
    def scan_plugin_manifests(self, base_dir: str = "store") -> List[Dict[str, Any]]:
        """扫描所有插件的 manifest.json 文件
        
        Returns:
            包含所有插件信息的列表，每个元素包含：
            - plugin_name: 插件名称
            - plugin_dir: 插件目录路径
            - manifest: manifest.json 内容
            - system_dependencies: 系统依赖列表
        """
        results = []
        base_path = Path(base_dir)
        
        if not base_path.exists():
            return results
        
        # 扫描所有插件目录
        for vendor_dir in base_path.iterdir():
            if not vendor_dir.is_dir():
                continue
            
            for plugin_dir in vendor_dir.iterdir():
                if not plugin_dir.is_dir():
                    continue
                
                manifest_file = plugin_dir / "manifest.json"
                if not manifest_file.exists():
                    continue
                
                try:
                    with open(manifest_file, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    
                    # 提取系统依赖
                    system_deps = manifest.get("system_dependencies", [])
                    
                    results.append({
                        "plugin_name": plugin_dir.name.rstrip("}"),
                        "plugin_dir": str(plugin_dir),
                        "manifest": manifest,
                        "system_dependencies": system_deps
                    })
                except Exception as e:
                    import traceback; print(f"[main.py] 错误:{type(e).__name__}:{e}"); traceback.print_exc()
                    continue
        
        return results
    
    def check_all_dependencies(self, base_dir: str = "store") -> Dict[str, Any]:
        """检查所有插件的系统依赖
        
        Args:
            base_dir: 基础扫描目录
            
        Returns:
            检查结果字典，包含：
            - total_plugins: 扫描的插件总数
            - plugins_with_deps: 有系统依赖的插件数
            - dependencies: 依赖检查结果列表
            - missing_count: 缺失的依赖数量
            - installed_count: 已安装的依赖数量
        """
        plugins = self.scan_plugin_manifests(base_dir)
        
        all_deps = {}  # {package: [plugin_names]}
        for plugin in plugins:
            for dep in plugin["system_dependencies"]:
                if dep not in all_deps:
                    all_deps[dep] = []
                all_deps[dep].append(plugin["plugin_name"])
        
        results = []
        installed_count = 0
        missing_count = 0
        
        for package, plugin_names in all_deps.items():
            is_installed = self.checker.check_package(package)
            if is_installed:
                installed_count += 1
            else:
                missing_count += 1
            
            results.append({
                "package": package,
                "installed": is_installed,
                "required_by": plugin_names
            })
        
        return {
            "total_plugins": len(plugins),
            "plugins_with_deps": sum(1 for p in plugins if p["system_dependencies"]),
            "dependencies": results,
            "missing_count": missing_count,
            "installed_count": installed_count
        }
    
    def install_missing_dependencies(self, base_dir: str = "store") -> Dict[str, Any]:
        """安装所有缺失的系统依赖
        
        Args:
            base_dir: 基础扫描目录
            
        Returns:
            安装结果字典，包含：
            - total_to_install: 需要安装的包数量
            - success_count: 成功安装的包数量
            - failed_count: 安装失败的包数量
            - results: 每个包的安装结果
        """
        check_result = self.check_all_dependencies(base_dir)
        
        to_install = [dep for dep in check_result["dependencies"] if not dep["installed"]]
        
        install_results = []
        success_count = 0
        failed_count = 0
        
        for dep in to_install:
            result = self.checker.check_and_install(dep["package"], auto_install=True)
            result["required_by"] = dep["required_by"]
            install_results.append(result)
            
            if result["success"]:
                success_count += 1
            else:
                failed_count += 1
        
        return {
            "total_to_install": len(to_install),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": install_results
        }
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        return {
            "package_manager": self.checker.detected_pm,
            "auto_install_enabled": self.auto_install,
            "scan_directories": self.scan_dirs
        }
    
    def register_pl_functions(self, injector: Any):
        """注册 PL 注入功能
        
        通过 PL 注入机制向插件加载器注册以下功能：
        - auto-dependency:scan: 扫描所有插件的系统依赖
        - auto-dependency:check: 检查依赖安装状态
        - auto-dependency:install: 安装缺失的依赖
        - auto-dependency:info: 获取插件系统信息
        """
        # 注册扫描功能
        def scan_deps(scan_dir: str = "store") -> Dict[str, Any]:
            """扫描所有插件的声明文件"""
            return self.scan_plugin_manifests(scan_dir)
        
        injector.register_function(
            "auto-dependency:scan",
            scan_deps,
            "扫描所有插件的声明文件，获取系统依赖列表"
        )
        
        # 注册检查功能
        def check_deps(scan_dir: str = "store") -> Dict[str, Any]:
            """检查所有系统依赖的安装状态"""
            return self.check_all_dependencies(scan_dir)
        
        injector.register_function(
            "auto-dependency:check",
            check_deps,
            "检查所有插件声明的系统依赖是否已安装"
        )
        
        # 注册安装功能
        def install_deps(scan_dir: str = "store") -> Dict[str, Any]:
            """安装所有缺失的系统依赖"""
            return self.install_missing_dependencies(scan_dir)
        
        injector.register_function(
            "auto-dependency:install",
            install_deps,
            "自动安装所有缺失的系统依赖"
        )
        
        # 注册信息功能
        def get_info() -> Dict[str, Any]:
            """获取插件系统信息"""
            return self.get_system_info()
        
        injector.register_function(
            "auto-dependency:info",
            get_info,
            "获取自动依赖插件的系统信息"
        )


def New() -> AutoDependencyPlugin:
    """创建插件实例"""
    return AutoDependencyPlugin()
