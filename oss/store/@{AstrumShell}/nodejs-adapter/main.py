"""
Node.js Runtime Adapter for AstrumShell
=====================================
This plugin acts as a pure service provider (Adapter). It does NOT contain its own business logic or pkg.
Instead, it exposes standard interfaces for OTHER plugins to execute Node.js/npm commands 
within THEIR own contexts (specifically their ./pkg directories).

Usage by other plugins:
    1. Get this adapter from the shared service registry.
    2. Call adapter.execute_in_context(plugin_root="./path/to/other-plugin", command="npm start")
    3. The adapter will automatically switch CWD to "./path/to/other-plugin/pkg" and run the command.
"""

import os
import sys
import json
import subprocess
import shutil
from typing import Dict, Any, List, Optional

class NodeJSAdapter:
    """
    Pure Node.js Runtime Adapter.
    Provides execution context switching for other plugins.
    """
    
    def __init__(self):
        self.name = "nodejs-adapter"
        self.version = "1.0.0"
        self.description = "Stateless Node.js runtime adapter for cross-plugin execution"
        self.node_path = None
        self.npm_path = None
        self._detect_runtime()
    
    def _detect_runtime(self):
        """Detect global Node.js and npm installation"""
        try:
            self.node_path = shutil.which('node')
            self.npm_path = shutil.which('npm')
            
            if not self.node_path:
                print("[WARNING] Node.js not found in global PATH")
            if not self.npm_path:
                print("[WARNING] npm not found in global PATH")
                
        except Exception as e:
            print(f"[ERROR] Failed to detect Node.js runtime: {type(e).__name__} - {e}")
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return available capabilities and runtime info"""
        versions = self.check_versions()
        return {
            'available': bool(self.node_path),
            'npm_available': bool(self.npm_path),
            'versions': versions,
            'features': ['run_script', 'install_deps', 'exec_command', 'context_switching']
        }

    def check_versions(self) -> Dict[str, str]:
        """Check Node.js and npm versions"""
        result = {}
        if self.node_path:
            try:
                result['node'] = subprocess.check_output([self.node_path, '--version'], stderr=subprocess.STDOUT).decode().strip()
            except Exception as e:
                result['node'] = f"Error: {type(e).__name__} - {e}"
        
        if self.npm_path:
            try:
                result['npm'] = subprocess.check_output([self.npm_path, '--version'], stderr=subprocess.STDOUT).decode().strip()
            except Exception as e:
                result['npm'] = f"Error: {type(e).__name__} - {e}"
        return result
    
    def execute_in_context(self, plugin_root: str, command_args: List[str], is_npm: bool = False) -> Dict[str, Any]:
        """
        CORE METHOD: Execute a command within the context of another plugin.
        
        Args:
            plugin_root: The root directory of the CALLING plugin (e.g., /workspace/oss/plugins/my-web-app)
            command_args: The command arguments (e.g., ['start'] or ['install', 'express'])
            is_npm: If True, uses 'npm'. If False, uses 'node'.
            
        Behavior:
            1. Targets the './pkg' subdirectory inside plugin_root.
            2. Sets cwd to that pkg directory.
            3. Executes the command.
            4. Ensures dependencies install into that specific pkg folder.
        """
        if not self.node_path:
            return {'success': False, 'error': 'Node.js runtime not found'}
        if is_npm and not self.npm_path:
            return {'success': False, 'error': 'npm not found'}

        # Determine the working directory: plugin_root/pkg
        work_dir = os.path.join(plugin_root, 'pkg')
        
        if not os.path.exists(work_dir):
            return {'success': False, 'error': f'Target pkg directory not found: {work_dir}'}

        try:
            # Construct command
            executable = self.npm_path if is_npm else self.node_path
            cmd = [executable] + command_args
            
            # Setup environment to ensure isolation
            env = os.environ.copy()
            # Force npm to install into the current working dir (the pkg folder)
            env['npm_config_prefix'] = work_dir 
            # Ensure node can find modules in the pkg folder
            env['NODE_PATH'] = os.path.join(work_dir, 'node_modules')

            print(f"[ADAPTER] Executing in context: {work_dir}")
            print(f"[ADAPTER] Command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                cwd=work_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 min timeout for installs
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'cwd': work_dir
            }
            
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Command execution timeout'}
        except Exception as e:
            return {'success': False, 'error': f'{type(e).__name__} - {e}'}

    def install_dependencies(self, plugin_root: str, packages: List[str] = None) -> Dict[str, Any]:
        """
        Helper: Install dependencies for a specific plugin.
        If packages is None, runs 'npm install' (installs from package.json).
        If packages is provided, runs 'npm install <pkg1> <pkg2>...'.
        """
        args = ['install']
        if packages:
            args.extend(packages)
        return self.execute_in_context(plugin_root, args, is_npm=True)

    def run_script(self, plugin_root: str, script_name: str, extra_args: List[str] = None) -> Dict[str, Any]:
        """
        Helper: Run an npm script (e.g., 'start', 'build') for a specific plugin.
        """
        args = ['run', script_name]
        if extra_args:
            args.append('--')
            args.extend(extra_args)
        return self.execute_in_context(plugin_root, args, is_npm=True)

    def run_file(self, plugin_root: str, file_path: str, args: List[str] = None) -> Dict[str, Any]:
        """
        Helper: Run a specific JS file within a plugin's pkg directory.
        file_path should be relative to the pkg dir (e.g., 'index.js').
        """
        cmd_args = [file_path]
        if args:
            cmd_args.extend(args)
        return self.execute_in_context(plugin_root, cmd_args, is_npm=False)

    def init_project(self, plugin_root: str, name: str = "plugin-project") -> Dict[str, Any]:
        """
        Helper: Initialize a package.json in the plugin's pkg directory.
        """
        # First run npm init -y
        res = self.execute_in_context(plugin_root, ['init', '-y'], is_npm=True)
        if not res['success']:
            return res
        
        # Then update the name to be more specific
        pkg_json_path = os.path.join(plugin_root, 'pkg', 'package.json')
        if os.path.exists(pkg_json_path):
            try:
                with open(pkg_json_path, 'r+', encoding='utf-8') as f:
                    data = json.load(f)
                    data['name'] = name
                    data['private'] = True
                    f.seek(0)
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.truncate()
                return {'success': True, 'message': f'Initialized project {name}'}
            except Exception as e:
                return {'success': False, 'error': f'Failed to update package.json: {e}'}
        return res


# --- Plugin Lifecycle Hooks ---

def init(context):
    """
    Initialize the adapter and register it as a shared service.
    This plugin does NOT start any server or run any code itself.
    It just registers the tool for others to use.
    """
    adapter = NodeJSAdapter()
    versions = adapter.check_versions()
    
    print(f"[INFO] Node.js Adapter Service Registered")
    if versions.get('node'):
        print(f"[INFO] Runtime: Node {versions['node']}")
    if versions.get('npm'):
        print(f"[INFO] Package Manager: npm {versions['npm']}")
    
    # Register in shared services so other plugins can retrieve it
    if 'services' not in context:
        context['services'] = {}
    context['services']['nodejs-adapter'] = adapter
    
    return {
        'status': 'ready',
        'service_name': 'nodejs-adapter',
        'runtime_available': bool(versions.get('node')),
        'versions': versions
    }

def start(context):
    """No-op: This is a stateless service provider."""
    return {'status': 'active'}

def stop(context):
    """No-op: Nothing to clean up."""
    return {'status': 'inactive'}

def get_info(context):
    """Return adapter capabilities."""
    adapter = context.get('services', {}).get('nodejs-adapter')
    if adapter:
        return adapter.get_capabilities()
    return {'error': 'Adapter service not found'}
