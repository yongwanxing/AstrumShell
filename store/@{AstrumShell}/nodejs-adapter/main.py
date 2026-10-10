"""
Node.js Adapter Plugin for AstrumShell

This plugin provides Node.js and npm capabilities to other plugins.
Other plugins can specify this adapter in their manifest to run Node.js projects
located in their /pkg directory with isolated dependencies.

Features:
- Install npm packages to plugin-specific directories
- Execute Node.js scripts and npm commands
- Check Node.js and npm versions
- List installed packages
- Dependency isolation per plugin
"""

import subprocess
import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any


class NodeJSAdapter:
    """Node.js runtime adapter for managing Node.js projects and dependencies."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Node.js adapter with configuration."""
        self.config = config or {}
        self.node_path = self.config.get('node_path', '/usr/bin/node')
        self.npm_path = self.config.get('npm_path', '/usr/bin/npm')
        self.default_registry = self.config.get('default_registry', 'https://registry.npmjs.org')
        self.cache_dir = Path(self.config.get('cache_dir', '~/.astrumshell/nodejs-cache')).expanduser()
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self._validate_runtime()
    
    def _validate_runtime(self) -> bool:
        """Validate that Node.js and npm are available."""
        try:
            node_result = subprocess.run(
                [self.node_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if node_result.returncode != 0:
                raise RuntimeError(f"Node.js not found: {node_result.stderr}")
            
            npm_result = subprocess.run(
                [self.npm_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if npm_result.returncode != 0:
                raise RuntimeError(f"npm not found: {npm_result.stderr}")
            
            return True
        except FileNotFoundError as e:
            raise RuntimeError(f"Node.js or npm not found in system: {str(e)}")
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"Timeout while checking Node.js/npm versions: {str(e)}")
    
    def check_versions(self) -> Dict[str, str]:
        """Check Node.js and npm versions."""
        try:
            node_result = subprocess.run(
                [self.node_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            npm_result = subprocess.run(
                [self.npm_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return {
                'node': node_result.stdout.strip(),
                'npm': npm_result.stdout.strip(),
                'status': 'ok'
            }
        except subprocess.TimeoutExpired as e:
            return {
                'node': 'unknown',
                'npm': 'unknown',
                'status': 'error',
                'error': f'Timeout: {str(e)}'
            }
        except Exception as e:
            return {
                'node': 'unknown',
                'npm': 'unknown',
                'status': 'error',
                'error': str(e)
            }
    
    def install(self, plugin_id: str, packages: List[str], 
                pkg_dir: Optional[Path] = None, 
                is_dev: bool = False) -> Dict[str, Any]:
        """
        Install npm packages to a plugin-specific directory.
        
        Args:
            plugin_id: Unique identifier for the plugin
            packages: List of npm packages to install (e.g., ['express', 'lodash@4.17.21'])
            pkg_dir: Optional custom package directory (defaults to plugin storage dir)
            is_dev: Whether to install as dev dependencies
        
        Returns:
            Dict with installation result
        """
        try:
            # Determine target directory
            if pkg_dir is None:
                # Default to plugin storage directory
                target_dir = self.cache_dir / plugin_id
            else:
                target_dir = Path(pkg_dir)
            
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Build npm install command
            cmd = [self.npm_path, 'install']
            if is_dev:
                cmd.append('--save-dev')
            else:
                cmd.append('--save')
            
            # Set registry if specified
            if self.default_registry:
                cmd.extend(['--registry', self.default_registry])
            
            # Add packages
            cmd.extend(packages)
            
            # Execute installation
            result = subprocess.run(
                cmd,
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout for installation
            )
            
            if result.returncode == 0:
                return {
                    'status': 'success',
                    'plugin_id': plugin_id,
                    'packages': packages,
                    'target_dir': str(target_dir),
                    'output': result.stdout,
                    'is_dev': is_dev
                }
            else:
                return {
                    'status': 'error',
                    'plugin_id': plugin_id,
                    'packages': packages,
                    'target_dir': str(target_dir),
                    'error': result.stderr,
                    'output': result.stdout
                }
        except subprocess.TimeoutExpired as e:
            return {
                'status': 'error',
                'plugin_id': plugin_id,
                'packages': packages,
                'error': f'Installation timeout: {str(e)}'
            }
        except Exception as e:
            return {
                'status': 'error',
                'plugin_id': plugin_id,
                'packages': packages,
                'error': str(e)
            }
    
    def run(self, plugin_id: str, script: str, 
            pkg_dir: Optional[Path] = None,
            args: Optional[List[str]] = None,
            env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Execute a Node.js script or npm command.
        
        Args:
            plugin_id: Unique identifier for the plugin
            script: Script to run (e.g., 'start', 'build', or path to .js file)
            pkg_dir: Optional custom package directory
            args: Additional arguments to pass
            env: Custom environment variables
        
        Returns:
            Dict with execution result
        """
        try:
            # Determine working directory
            if pkg_dir is None:
                work_dir = self.cache_dir / plugin_id
            else:
                work_dir = Path(pkg_dir)
            
            if not work_dir.exists():
                return {
                    'status': 'error',
                    'error': f'Plugin directory not found: {work_dir}'
                }
            
            # Determine if it's an npm script or direct node execution
            if script.endswith('.js') or script.endswith('.ts'):
                # Direct Node.js execution
                cmd = [self.node_path, script]
                if args:
                    cmd.extend(args)
            else:
                # NPM script execution
                cmd = [self.npm_path, 'run', script]
                if args:
                    cmd.append('--')
                    cmd.extend(args)
            
            # Prepare environment
            run_env = os.environ.copy()
            if env:
                run_env.update(env)
            
            # Execute
            result = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=300,
                env=run_env
            )
            
            return {
                'status': 'success' if result.returncode == 0 else 'error',
                'plugin_id': plugin_id,
                'script': script,
                'exit_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'work_dir': str(work_dir)
            }
        except subprocess.TimeoutExpired as e:
            return {
                'status': 'error',
                'plugin_id': plugin_id,
                'script': script,
                'error': f'Execution timeout: {str(e)}'
            }
        except Exception as e:
            return {
                'status': 'error',
                'plugin_id': plugin_id,
                'script': script,
                'error': str(e)
            }
    
    def list_packages(self, plugin_id: str, 
                      pkg_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        List installed packages in a plugin directory.
        
        Args:
            plugin_id: Unique identifier for the plugin
            pkg_dir: Optional custom package directory
        
        Returns:
            Dict with list of installed packages
        """
        try:
            # Determine working directory
            if pkg_dir is None:
                work_dir = self.cache_dir / plugin_id
            else:
                work_dir = Path(pkg_dir)
            
            if not work_dir.exists():
                return {
                    'status': 'error',
                    'error': f'Plugin directory not found: {work_dir}'
                }
            
            # Run npm list
            result = subprocess.run(
                [self.npm_path, 'list', '--json', '--depth=0'],
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                try:
                    packages = json.loads(result.stdout)
                    return {
                        'status': 'success',
                        'plugin_id': plugin_id,
                        'packages': packages.get('dependencies', {}),
                        'work_dir': str(work_dir)
                    }
                except json.JSONDecodeError as e:
                    return {
                        'status': 'error',
                        'plugin_id': plugin_id,
                        'error': f'Failed to parse npm list output: {str(e)}',
                        'raw_output': result.stdout
                    }
            else:
                return {
                    'status': 'error',
                    'plugin_id': plugin_id,
                    'error': result.stderr,
                    'work_dir': str(work_dir)
                }
        except subprocess.TimeoutExpired as e:
            return {
                'status': 'error',
                'plugin_id': plugin_id,
                'error': f'Timeout listing packages: {str(e)}'
            }
        except Exception as e:
            return {
                'status': 'error',
                'plugin_id': plugin_id,
                'error': str(e)
            }
    
    def init_project(self, plugin_id: str, pkg_dir: Optional[Path] = None,
                     package_name: Optional[str] = None,
                     version: str = "1.0.0") -> Dict[str, Any]:
        """
        Initialize a new Node.js project in a plugin directory.
        
        Args:
            plugin_id: Unique identifier for the plugin
            pkg_dir: Optional custom package directory
            package_name: Optional package name (defaults to plugin_id)
            version: Package version
        
        Returns:
            Dict with initialization result
        """
        try:
            # Determine working directory
            if pkg_dir is None:
                work_dir = self.cache_dir / plugin_id
            else:
                work_dir = Path(pkg_dir)
            
            work_dir.mkdir(parents=True, exist_ok=True)
            
            # Create package.json
            package_json = {
                'name': package_name or plugin_id.replace('/', '-'),
                'version': version,
                'description': f'Node.js project for plugin {plugin_id}',
                'main': 'index.js',
                'scripts': {
                    'start': 'node index.js',
                    'test': 'echo "Error: no test specified" && exit 1'
                },
                'keywords': [],
                'author': '',
                'license': 'ISC'
            }
            
            package_json_path = work_dir / 'package.json'
            with open(package_json_path, 'w', encoding='utf-8') as f:
                json.dump(package_json, f, indent=2)
            
            # Create basic index.js
            index_js_path = work_dir / 'index.js'
            with open(index_js_path, 'w', encoding='utf-8') as f:
                f.write('// Node.js project for AstrumShell plugin\n')
                f.write(f'// Plugin ID: {plugin_id}\n')
                f.write('console.log("Hello from AstrumShell Node.js plugin!");\n')
            
            return {
                'status': 'success',
                'plugin_id': plugin_id,
                'work_dir': str(work_dir),
                'package_json': str(package_json_path),
                'index_js': str(index_js_path)
            }
        except Exception as e:
            return {
                'status': 'error',
                'plugin_id': plugin_id,
                'error': str(e)
            }


# Plugin lifecycle hooks
def init(config: Dict[str, Any]) -> NodeJSAdapter:
    """Initialize the Node.js adapter plugin."""
    adapter = NodeJSAdapter(config)
    return adapter


def get_capabilities() -> List[str]:
    """Return the capabilities provided by this plugin."""
    return [
        'nodejs_runtime',
        'npm_package_manager',
        'dependency_isolation',
        'script_execution',
        'project_initialization'
    ]


def execute_command(adapter: NodeJSAdapter, command: str, **kwargs) -> Dict[str, Any]:
    """
    Execute a command through the adapter.
    
    Available commands:
    - check_versions: Check Node.js and npm versions
    - install: Install npm packages
    - run: Execute Node.js scripts or npm commands
    - list_packages: List installed packages
    - init_project: Initialize a new Node.js project
    """
    if command == 'check_versions':
        return adapter.check_versions()
    elif command == 'install':
        return adapter.install(**kwargs)
    elif command == 'run':
        return adapter.run(**kwargs)
    elif command == 'list_packages':
        return adapter.list_packages(**kwargs)
    elif command == 'init_project':
        return adapter.init_project(**kwargs)
    else:
        return {
            'status': 'error',
            'error': f'Unknown command: {command}'
        }


if __name__ == '__main__':
    # Test the adapter
    print("Node.js Adapter Plugin for AstrumShell")
    print("=" * 50)
    
    adapter = init({})
    
    # Check versions
    versions = adapter.check_versions()
    print(f"\nNode.js Version: {versions.get('node', 'N/A')}")
    print(f"npm Version: {versions.get('npm', 'N/A')}")
    
    # Get capabilities
    caps = get_capabilities()
    print(f"\nCapabilities: {', '.join(caps)}")
    
    print("\n✓ Node.js Adapter initialized successfully!")
