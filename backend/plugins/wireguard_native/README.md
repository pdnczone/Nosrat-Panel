# WireGuard Native Plugin (Example)

A minimal example plugin showing how to integrate a new tunnel type
with nosrat-panel.

## What it does

This plugin manages a **native WireGuard tunnel** using `wg-quick`.
It demonstrates the full plugin lifecycle:
- `create()` - Generate keypair, write config
- `start()` / `stop()` / `restart()` - Control the interface
- `status()` - Read transfer stats from `wg show`
- `logs()` - Tail systemd journal
- `destroy()` - Clean up

## Files

```
wireguard_native/
├── __init__.py         # Exports WireGuardNativePlugin
├── plugin.py           # Main implementation
├── manifest.json       # Plugin metadata
├── wizard_schema.json  # Frontend form schema
└── README.md           # This file
```

## How to install

Just copy this folder to `backend/plugins/wireguard_native/`
in your nosrat-panel installation. The plugin loader
will auto-discover it on next backend restart.

```bash
sudo systemctl restart nosrat-panel-backend
```

## How to use

1. Open the nosrat-panel web UI
2. Go to **Tunnels** → **+ Create Tunnel**
3. Select **WireGuard (Native)** from the tunnel type list
4. Fill in the wizard:
   - Server Endpoint
   - Listen Port (default 51820)
   - Client Address
   - DNS Servers
   - Allowed IPs
5. Click **Create**
6. The plugin generates a keypair and creates `/etc/wireguard/wgN.conf`
7. **Copy the public key** to your WireGuard server's `[Peer]` section
8. Click **Start** to bring the interface up

## Production notes

- For remote servers, this plugin assumes the panel can run `wg` commands directly
  (i.e., the panel runs on the same host as the tunnel, OR uses SSH under the hood
  via `Plugin._run_remote` — see the `gre_ipsec` plugin for the SSH pattern)
- Keypairs are stored in the config file with `0600` perms
- For multi-server support, you'd need to add `server_id` handling and SSH

## Using as a template

To create your own plugin:

1. Copy this folder to a new name (e.g., `my_custom_tunnel/`)
2. Update `manifest.json` with your metadata
3. Update `wizard_schema.json` with your form fields
4. Rewrite `plugin.py` for your tunnel's lifecycle
5. Update `__init__.py` to export your plugin class

The plugin loader will pick it up automatically. No core code changes needed.
