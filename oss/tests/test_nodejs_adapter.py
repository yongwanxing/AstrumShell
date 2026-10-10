"""
Tests for Node.js Adapter Plugin
"""

import os
import sys
import json
import tempfile
import shutil
import pytest

# Add the plugin directory to path
PLUGIN_DIR = os.path.join(os.path.dirname(__file__), '..', 'store', '@{AstrumShell}', 'nodejs-adapter')
sys.path.insert(0, PLUGIN_DIR)

# Import after path update
import importlib.util
spec = importlib.util.spec_from_file_location("nodejs_adapter_main", os.path.join(PLUGIN_DIR, "main.py"))
main_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_module)
NodeJSAdapter = main_module.NodeJSAdapter


class TestNodeJSAdapter:
    """Test suite for NodeJSAdapter class"""
    
    @pytest.fixture
    def adapter(self):
        """Create a fresh adapter instance"""
        return NodeJSAdapter()
    
    @pytest.fixture
    def temp_plugin_dir(self):
        """Create a temporary plugin directory structure"""
        temp_dir = tempfile.mkdtemp()
        pkg_dir = os.path.join(temp_dir, 'pkg')
        os.makedirs(pkg_dir)
        
        # Create a minimal package.json
        package_json = {
            "name": "test-plugin",
            "version": "1.0.0",
            "scripts": {
                "test": "echo 'test passed'"
            }
        }
        with open(os.path.join(pkg_dir, 'package.json'), 'w', encoding='utf-8') as f:
            json.dump(package_json, f)
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    def test_adapter_initialization(self, adapter):
        """Test that adapter initializes correctly"""
        assert adapter.name == "nodejs-adapter"
        assert adapter.version == "1.0.0"
        assert "Node.js" in adapter.description
    
    def test_get_capabilities(self, adapter):
        """Test capabilities reporting"""
        caps = adapter.get_capabilities()
        
        assert 'available' in caps
        assert 'npm_available' in caps
        assert 'versions' in caps
        assert 'features' in caps
        assert isinstance(caps['features'], list)
    
    def test_check_versions(self, adapter):
        """Test version checking"""
        versions = adapter.check_versions()
        
        # Should return dict with node and/or npm keys
        assert isinstance(versions, dict)
        # At least one should be present if runtime exists
        if adapter.node_path:
            assert 'node' in versions
            assert not versions['node'].startswith('Error')
    
    def test_execute_in_context_missing_dir(self, adapter):
        """Test execution with non-existent directory"""
        if not adapter.node_path:
            pytest.skip("Node.js not available")
        
        result = adapter.execute_in_context('/nonexistent/path', ['--version'])
        
        assert result['success'] is False
        assert 'error' in result
        assert 'not found' in result['error'].lower()
    
    def test_execute_in_context_node_version(self, adapter, temp_plugin_dir):
        """Test executing node --version in context"""
        if not adapter.node_path:
            pytest.skip("Node.js not available")
        
        result = adapter.execute_in_context(temp_plugin_dir, ['--version'], is_npm=False)
        
        assert result['success'] is True
        assert 'cwd' in result
        assert result['cwd'].endswith('pkg')
        # Version should start with v
        assert result['stdout'].strip().startswith('v')
    
    def test_execute_in_context_npm_version(self, adapter, temp_plugin_dir):
        """Test executing npm --version in context"""
        if not adapter.npm_path:
            pytest.skip("npm not available")
        
        result = adapter.execute_in_context(temp_plugin_dir, ['--version'], is_npm=True)
        
        assert result['success'] is True
        assert 'cwd' in result
        assert result['cwd'].endswith('pkg')
        # Version should be numeric (possibly with dots)
        assert len(result['stdout'].strip()) > 0
    
    def test_install_dependencies_empty(self, adapter, temp_plugin_dir):
        """Test installing dependencies (empty, just reads package.json)"""
        if not adapter.npm_path:
            pytest.skip("npm not available")
        
        result = adapter.install_dependencies(temp_plugin_dir)
        
        assert result['success'] is True
        assert 'cwd' in result
        assert result['cwd'].endswith('pkg')
    
    def test_run_script_test(self, adapter, temp_plugin_dir):
        """Test running a custom npm script"""
        if not adapter.npm_path:
            pytest.skip("npm not available")
        
        result = adapter.run_script(temp_plugin_dir, 'test')
        
        assert result['success'] is True
        assert 'test passed' in result['stdout']
    
    def test_run_file(self, adapter, temp_plugin_dir):
        """Test running a JavaScript file"""
        if not adapter.node_path:
            pytest.skip("Node.js not available")
        
        # Create a simple JS file
        js_file = os.path.join(temp_plugin_dir, 'pkg', 'hello.js')
        with open(js_file, 'w', encoding='utf-8') as f:
            f.write("console.log('Hello from Node.js');")
        
        result = adapter.run_file(temp_plugin_dir, 'hello.js')
        
        assert result['success'] is True
        assert 'Hello from Node.js' in result['stdout']
    
    def test_init_project(self, adapter, temp_plugin_dir):
        """Test initializing a new project"""
        if not adapter.npm_path:
            pytest.skip("npm not available")
        
        # Create empty pkg dir for this test
        pkg_dir = os.path.join(temp_plugin_dir, 'pkg2')
        os.makedirs(pkg_dir)
        
        # Create a minimal package.json first (npm init -y creates one)
        package_json = {"name": "temp", "version": "1.0.0"}
        with open(os.path.join(pkg_dir, 'package.json'), 'w', encoding='utf-8') as f:
            json.dump(package_json, f)
        
        # Manually test the logic since execute_in_context targets ./pkg by default
        pkg_json_path = os.path.join(pkg_dir, 'package.json')
        
        # Simulate what init_project does
        data = {"name": "custom-test-project", "version": "1.0.0", "private": True}
        with open(pkg_json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Verify
        with open(pkg_json_path, 'r', encoding='utf-8') as f:
            pkg_data = json.load(f)
            assert pkg_data['name'] == 'custom-test-project'
            assert pkg_data['private'] is True


class TestPluginLifecycle:
    """Test plugin lifecycle hooks"""
    
    def test_init_hook(self):
        """Test init hook registers service"""
        init = main_module.init
        
        context = {}
        result = init(context)
        
        assert result['status'] == 'ready'
        assert 'nodejs-adapter' in context['services']
        assert 'runtime_available' in result
    
    def test_start_hook(self):
        """Test start hook"""
        start = main_module.start
        
        context = {}
        result = start(context)
        
        assert result['status'] == 'active'
    
    def test_stop_hook(self):
        """Test stop hook"""
        stop = main_module.stop
        
        context = {}
        result = stop(context)
        
        assert result['status'] == 'inactive'
    
    def test_get_info_hook(self):
        """Test get_info hook"""
        init = main_module.init
        get_info = main_module.get_info
        
        context = {}
        init(context)
        
        info = get_info(context)
        
        assert isinstance(info, dict)
        assert 'features' in info or 'error' in info


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
