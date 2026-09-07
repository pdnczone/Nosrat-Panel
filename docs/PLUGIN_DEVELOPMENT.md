# Plugin Development Guide

Learn how to create custom tunnel types for nosrat-panel.

---

## Overview

nosrat-panel has a **plugin system** that allows you to add new tunnel types without modifying the core code. Plugins are automatically discovered at startup and their UI is rendered dynamically from a JSON schema.

---

## Quick Start

### 1. Create Plugin Folder

```bash
mkdir -p backend/plugins/my_tunnel
cd backend/plugins/my_tunnel
```

### 2. Create `__init__.py`

```python
"""My custom tunnel plugin."""
from .plugin import MyTunnelPlugin

__all__ = ["MyTunnelPlugin"]
```

### 3. Create `manifest.json`

```json
{
  "id": "my_tunnel",
  "version": "1.0.0",
  "name": "My Custom Tunnel",
  "description": "Brief description of what this tunnel does",
  "icon": "🚀",
  "category": "tunnel",
  "entry": "plugin.py",
  "wizard_schema": "./wizard_schema.json",
  "dependencies": ["some-system-package"],
  "author": "Your Name",
  "homepage": "https://github.com/you/my-tunnel"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | ✅ | Unique identifier (lowercase, no spaces) |
| `version` | ✅ | Semver version |
| `name` | ✅ | Display name |
| `description` | ✅ | Short description (1 sentence) |
| `icon` | ❌ | Emoji or icon URL |
| `category` | ✅ | Always `"tunnel"` for now |
| `entry` | ✅ | Python file containing the plugin class |
| `wizard_schema` | ✅ | Path to wizard form JSON schema |
| `dependencies` | ❌ | System packages required |
| `author` | ❌ | Your name |
| `homepage` | ❌ | URL |

### 4. Create `wizard_schema.json`

This defines the form fields shown in the frontend wizard:

```json
{
  "title": "My Custom Tunnel",
  "description": "Configure your custom tunnel",
  "fields": [
    {
      "key": "remote_host",
      "label": "Remote Host",
      "type": "text",
      "required": true,
      "validation": "ipv4",
      "placeholder": "1.2.3.4",
      "help": "The IP address of the remote server"
    },
    {
      "key": "remote_port",
      "label": "Remote Port",
      "type": "number",
      "required": true,
      "default": 51820,
      "min": 1,
      "max": 65535
    },
    {
      "key": "protocol",
      "label": "Protocol",
      "type": "select",
      "required": true,
      "default": "udp",
      "options": [
        {"value": "tcp", "label": "TCP"},
        {"value": "udp", "label": "UDP"}
      ]
    },
    {
      "key": "use_encryption",
      "label": "Enable Encryption",
      "type": "switch",
      "default": true
    }
  ]
}
```

#### Supported Field Types

| Type | Description | Extra Props |
|------|-------------|-------------|
| `text` | Text input | `validation` (ipv4, ipv6, hostname, port) |
| `number` | Number input | `min`, `max`, `step` |
| `select` | Dropdown | `options: [{value, label}]` |
| `switch` | Boolean toggle | - |
| `textarea` | Multi-line text | `rows` |
| `password` | Password input | - |
| `multiselect` | Multi-select | `options: [...]` |

#### Validation Options

- `ipv4`: Must be valid IPv4
- `ipv6`: Must be valid IPv6
- `hostname`: Must be valid hostname
- `port`: 1-65535
- `email`: Must be valid email
- `url`: Must be valid URL

### 5. Implement `plugin.py`

```python
"""My custom tunnel plugin implementation."""
from typing import Dict, Any
from pathlib import Path
import json

from plugins.base import PluginBase, PluginMetadata


class MyTunnelPlugin(PluginBase):
    """Manages my custom tunnel type."""

    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="my_tunnel",
            name="My Custom Tunnel",
            description="Brief description",
            version="1.0.0",
            icon="🚀"
        )

    def get_wizard_schema(self) -> Dict[str, Any]:
        schema_path = Path(__file__).parent / "wizard_schema.json"
        with open(schema_path) as f:
            return json.load(f)

    async def create(self, tunnel_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create the tunnel configuration on the server.
        
        Args:
            tunnel_id: Unique ID for this tunnel instance
            params: Validated wizard params
            
        Returns:
            Dict with at least: {"config_path": "/etc/...", "status": "created"}
        """
        config_dir = Path("/etc/my-tunnel")
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config = f"""# My Tunnel config
remote_host = {params['remote_host']}
remote_port = {params['remote_port']}
protocol = {params['protocol']}
encrypted = {params.get('use_encryption', True)}
"""
        
        config_path = config_dir / f"{tunnel_id}.conf"
        config_path.write_text(config)
        
        return {
            "config_path": str(config_path),
            "status": "created"
        }

    async def start(self, tunnel_id: str) -> bool:
        """Start the tunnel. Return True on success."""
        result = await self._run_remote(
            f"systemctl start my-tunnel@{tunnel_id}"
        )
        return result.returncode == 0

    async def stop(self, tunnel_id: str) -> bool:
        """Stop the tunnel. Return True on success."""
        result = await self._run_remote(
            f"systemctl stop my-tunnel@{tunnel_id}"
        )
        return result.returncode == 0

    async def status(self, tunnel_id: str) -> Dict[str, Any]:
        """Get current tunnel status."""
        result = await self._run_remote(
            f"systemctl is-active my-tunnel@{tunnel_id}"
        )
        is_active = result.stdout.strip() == "active"
        
        return {
            "status": "active" if is_active else "inactive",
            "uptime": None,  # Optional: parse `systemctl show`
            "traffic_in": 0,  # Optional: read from /sys/class/net/
            "traffic_out": 0,
        }

    async def logs(self, tunnel_id: str, lines: int = 50) -> str:
        """Return recent log lines."""
        result = await self._run_remote(
            f"journalctl -u my-tunnel@{tunnel_id} -n {lines} --no-pager"
        )
        return result.stdout

    async def destroy(self, tunnel_id: str) -> bool:
        """Remove the tunnel configuration and clean up."""
        await self.stop(tunnel_id)
        config_path = Path(f"/etc/my-tunnel/{tunnel_id}.conf")
        if config_path.exists():
            config_path.unlink()
        return True
```

---

## Plugin API Reference

### `PluginBase` Class

Your plugin must inherit from `PluginBase` and implement these methods:

#### `metadata() -> PluginMetadata`
Return plugin metadata.

#### `get_wizard_schema() -> Dict`
Return the wizard form schema. Usually loads from `wizard_schema.json`.

#### `async create(tunnel_id, params) -> Dict`
Called when user creates a new tunnel.
- **Args**: `tunnel_id` (str), `params` (validated dict)
- **Returns**: Dict with `config_path` and `status`

#### `async start(tunnel_id) -> bool`
Start the tunnel. Return `True` on success.

#### `async stop(tunnel_id) -> bool`
Stop the tunnel. Return `True` on success.

#### `async status(tunnel_id) -> Dict`
Return current status with these optional keys:
- `status`: "active" | "inactive" | "error"
- `uptime`: seconds (int)
- `traffic_in`: bytes (int)
- `traffic_out`: bytes (int)
- `error_message`: str (if status == "error")

#### `async logs(tunnel_id, lines=50) -> str`
Return recent log lines as a string.

#### `async destroy(tunnel_id) -> bool`
Remove configuration and clean up. Return `True` on success.

### Helper: `self._run_remote(command)`

Runs a command on the remote server via SSH. Returns an async result with:
- `returncode` (int)
- `stdout` (str)
- `stderr` (str)

```python
result = await self._run_remote("ip addr show")
if result.returncode == 0:
    interfaces = result.stdout
```

---

## Example: WireGuard Native Plugin

See `backend/plugins/wireguard_native/` for a complete, working example. It demonstrates:
- Simple wg-quick integration
- QR code generation for clients
- Minimal dependencies (just `wireguard-tools`)

---

## Testing Your Plugin

```python
# backend/tests/test_my_plugin.py
import pytest
from backend.plugins.my_tunnel import MyTunnelPlugin

@pytest.mark.asyncio
async def test_create():
    plugin = MyTunnelPlugin()
    result = await plugin.create(
        tunnel_id="test1",
        params={"remote_host": "1.2.3.4", "remote_port": 51820}
    )
    assert result["status"] == "created"
    assert "config_path" in result
```

---

## Distributing Your Plugin

You can distribute plugins as:
1. **PR to nosrat-panel** (recommended for quality control)
2. **Standalone PyPI package** with a custom loader
3. **Git submodule** in `backend/plugins/`

---

## Best Practices

1. **Validate inputs** - Don't trust wizard params blindly
2. **Handle errors gracefully** - Return `False` or `{"status": "error", "error_message": "..."}`
3. **Use `run_with_timeout`** - All SSH commands should have timeouts
4. **Log everything** - Use Python's `logging` module
5. **Don't store secrets in config files** - Use separate `secrets/` directory with 0600 perms
6. **Test on real servers** - Unit tests aren't enough
7. **Document all params** - Use `help` field in wizard schema
8. **Make icons descriptive** - Users see them in the UI

---

## Need Help?

- 💬 [Telegram Support](https://t.me/dncdirect)
- 📖 [API Reference](API.md)
- 🐛 [Report an Issue](https://github.com/pdnczone/nosrat-panel/issues)
