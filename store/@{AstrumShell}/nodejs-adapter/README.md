# Node.js Adapter Plugin for AstrumShell

## Overview

The `@AstrumShell/nodejs-adapter` plugin provides Node.js and npm capabilities to other AstrumShell plugins. It enables any plugin to run Node.js projects located in their `/pkg` directory with isolated dependencies.

## Features

- **Node.js Runtime**: Execute Node.js scripts and applications
- **npm Package Manager**: Install and manage npm packages
- **Dependency Isolation**: Each plugin gets its own isolated `node_modules` directory
- **Script Execution**: Run npm scripts or direct Node.js files
- **Project Initialization**: Automatically create package.json and basic project structure

## Installation

The plugin is included in the AstrumShell store at:
```
store/@{AstrumShell}/nodejs-adapter/
```

It will be automatically loaded when the AstrumShell server starts.

## Usage

### For Plugin Developers

To use the Node.js adapter in your plugin, specify it in your plugin's manifest:

```json
{
  "name": "@AstrumShell/my-nodejs-plugin",
  "version": "1.0.0",
  "runtime": {
    "type": "nodejs",
    "entry_point": "pkg/index.js",
    "adapter": "@AstrumShell/nodejs-adapter"
  },
  "dependencies": {
    "nodejs-adapter": "^1.2.0"
  },
  "nodejs": {
    "packages": ["express", "lodash"],
    "scripts": {
      "start": "node index.js",
      "build": "webpack --mode production"
    }
  }
}
```

### Directory Structure

```
my-plugin/
├── manifest.json
├── main.py (optional Python entry point)
└── pkg/
    ├── package.json
    ├── index.js
    └── node_modules/ (auto-generated)
```

### API Methods

The adapter provides the following methods that can be called by other plugins:

#### `check_versions()`
Check Node.js and npm versions installed on the system.

```python
adapter = get_plugin('nodejs-adapter')
versions = adapter.check_versions()
# Returns: {'node': 'v20.19.5', 'npm': '10.8.2', 'status': 'ok'}
```

#### `install(plugin_id, packages, pkg_dir=None, is_dev=False)`
Install npm packages to a plugin-specific directory.

```python
result = adapter.install(
    plugin_id='my-plugin',
    packages=['express', 'lodash@4.17.21'],
    is_dev=False
)
# Returns: {'status': 'success', 'target_dir': '/path/to/dir', ...}
```

#### `run(plugin_id, script, pkg_dir=None, args=None, env=None)`
Execute a Node.js script or npm command.

```python
# Run npm script
result = adapter.run(
    plugin_id='my-plugin',
    script='start'  # runs 'npm run start'
)

# Run direct Node.js file
result = adapter.run(
    plugin_id='my-plugin',
    script='pkg/index.js',  # runs 'node pkg/index.js'
    args=['--port', '3000']
)
```

#### `list_packages(plugin_id, pkg_dir=None)`
List installed packages in a plugin directory.

```python
packages = adapter.list_packages(plugin_id='my-plugin')
# Returns: {'status': 'success', 'packages': {...}}
```

#### `init_project(plugin_id, pkg_dir=None, package_name=None, version='1.0.0')`
Initialize a new Node.js project.

```python
result = adapter.init_project(
    plugin_id='my-plugin',
    package_name='my-awesome-plugin'
)
# Creates package.json and index.js in the plugin directory
```

## Configuration

The adapter can be configured via environment variables or plugin config:

```json
{
  "config": {
    "node_path": "/usr/bin/node",
    "npm_path": "/usr/bin/npm",
    "default_registry": "https://registry.npmjs.org",
    "cache_dir": "~/.astrumshell/nodejs-cache"
  }
}
```

### Environment Variables

- `NODEJS_ADAPTER_NODE_PATH`: Path to Node.js binary
- `NODEJS_ADAPTER_NPM_PATH`: Path to npm binary
- `NODEJS_ADAPTER_REGISTRY`: Custom npm registry URL
- `NODEJS_ADAPTER_CACHE_DIR`: Directory for cached packages

## Examples

### Example 1: Simple Express Server Plugin

```json
{
  "name": "@AstrumShell/express-server",
  "version": "1.0.0",
  "runtime": {
    "type": "nodejs",
    "entry_point": "pkg/server.js",
    "adapter": "@AstrumShell/nodejs-adapter"
  },
  "nodejs": {
    "packages": ["express"]
  }
}
```

**pkg/server.js**:
```javascript
const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

app.get('/', (req, res) => {
  res.json({ message: 'Hello from AstrumShell!' });
});

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
```

### Example 2: Build Tool Plugin

```json
{
  "name": "@AstrumShell/webpack-builder",
  "version": "1.0.0",
  "runtime": {
    "type": "nodejs",
    "adapter": "@AstrumShell/nodejs-adapter"
  },
  "nodejs": {
    "packages": ["webpack", "webpack-cli"],
    "scripts": {
      "build": "webpack --mode production"
    }
  }
}
```

## Dependency Isolation

Each plugin gets its own isolated `node_modules` directory:

- Default location: `~/.astrumshell/nodejs-cache/{plugin_id}/`
- Custom location: Specify `pkg_dir` parameter in API calls
- No conflicts between different plugins' dependencies

## Error Handling

All adapter methods return a status object:

```python
result = adapter.install(plugin_id='test', packages=['invalid-package-name-xyz'])
if result['status'] == 'error':
    print(f"Installation failed: {result['error']}")
else:
    print(f"Success! Packages installed to: {result['target_dir']}")
```

## Testing

Test the adapter directly:

```bash
cd /workspace/store/@{AstrumShell}/nodejs-adapter
python main.py
```

Expected output:
```
Node.js Adapter Plugin for AstrumShell
==================================================

Node.js Version: v20.19.5
npm Version: 10.8.2

Capabilities: nodejs_runtime, npm_package_manager, dependency_isolation, script_execution, project_initialization

✓ Node.js Adapter initialized successfully!
```

## Troubleshooting

### Node.js or npm not found

Ensure Node.js and npm are installed on your system:

```bash
# Check installation
node --version
npm --version

# Install if needed (Ubuntu/Debian)
apt update && apt install -y nodejs npm

# Install if needed (macOS)
brew install node
```

### Permission errors

If you encounter permission errors during package installation:

```bash
# Ensure cache directory is writable
mkdir -p ~/.astrumshell/nodejs-cache
chmod 755 ~/.astrumshell/nodejs-cache
```

### Timeout during installation

For large packages or slow networks, increase the timeout in the adapter configuration.

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! Please read CONTRIBUTING.md for guidelines.
