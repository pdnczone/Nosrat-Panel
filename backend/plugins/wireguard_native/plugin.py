"""WireGuard native plugin - simple wg-quick wrapper."""
from __future__ import annotations

from typing import Any

from core.remote_exec import (
    apply_tunnel_config,
    run_on_both_endpoints,
    run_on_server,
    start_tunnel,
    stop_tunnel,
    tunnel_status,
)
from db.models import Server, Tunnel
from plugins.base import Plugin


class WireGuardNativePlugin(Plugin):
    """Manages a native WireGuard tunnel using wg-quick."""

    name = "wireguard_native"
    display_name = "WireGuard (Native)"
    description = "Native WireGuard tunnel without obfuscation - simple and fast"
    icon = "🔌"

    def get_wizard_schema(self) -> dict[str, Any]:
        import json
        from pathlib import Path

        schema_path = Path(__file__).parent / "wizard_schema.json"
        with open(schema_path) as f:
            return json.load(f)

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def create(
        self, tunnel: Tunnel | None, local: Server, remote: Server, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Create WireGuard config on both endpoints."""
        cfg = self._build_wg_config(tunnel, local, remote, params)

        # Send config to both endpoints
        local_res, remote_res = await apply_tunnel_config(local, remote, self.name, cfg)

        return {
            "local": local_res,
            "remote": remote_res,
            "status": "created",
        }

    async def start(
        self, tunnel: Tunnel, local: Server, remote: Server
    ) -> dict[str, Any]:
        """Bring up WireGuard on both endpoints."""
        local_res, remote_res = await start_tunnel(local, remote, self.name)
        return {
            "local": local_res,
            "remote": remote_res,
        }

    async def stop(
        self, tunnel: Tunnel, local: Server, remote: Server
    ) -> dict[str, Any]:
        """Bring down WireGuard on both endpoints."""
        local_res, remote_res = await stop_tunnel(local, remote, self.name)
        return {
            "local": local_res,
            "remote": remote_res,
        }

    async def restart(
        self, tunnel: Tunnel, local: Server, remote: Server
    ) -> dict[str, Any]:
        """Restart the tunnel on both endpoints."""
        await self.stop(tunnel, local, remote)
        return await self.start(tunnel, local, remote)

    async def status(
        self, tunnel: Tunnel, local: Server, remote: Server
    ) -> dict[str, Any]:
        """Get WireGuard status from both endpoints."""
        local_res, remote_res = await tunnel_status(local, remote, self.name)
        return {
            "local": local_res,
            "remote": remote_res,
        }

    async def logs(
        self, tunnel: Tunnel, local: Server, remote: Server, *, lines: int = 100
    ) -> str:
        """Get recent WireGuard logs from both endpoints."""
        local_res, remote_res = await run_on_both_endpoints(
            local, remote, "journalctl", ["-u", f"wg-quick@wg{tunnel.id}", "-n", str(lines), "--no-pager"]
        )
        return f"=== {local.name} ===\n{local_res.get('stdout', '')}\n\n=== {remote.name} ===\n{remote_res.get('stdout', '')}"

    async def destroy(
        self, tunnel: Tunnel, local: Server, remote: Server
    ) -> dict[str, Any]:
        """Remove WireGuard configuration on both endpoints."""
        local_res, remote_res = await run_on_both_endpoints(
            local, remote, "destroy_tunnel", [self.name]
        )
        return {
            "local": local_res,
            "remote": remote_res,
            "destroyed": True,
        }

    # ── Internal helpers ────────────────────────────────────────────────

    def _build_wg_config(
        self, tunnel: Tunnel, local: Server, remote: Server, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Build full WireGuard configuration for both endpoints."""
        # Determine which endpoint gets which keys
        # For simplicity, each endpoint generates its own keypair locally
        # In real deployment, the controller would generate and distribute keys
        return {
            "plugin": self.name,
            "tunnel_id": tunnel.id,
            "interface": f"wg{tunnel.id}",
            "listen_port": params.get("listen_port", 51820),
            "local": {
                "address": params["local_address"],  # e.g. "10.200.0.1/32"
                "mtu": 1420,
            },
            "remote": {
                "endpoint": f"{remote.host}:{params.get('remote_port', 51820)}",
                "public_key": "<REMOTE_PUBLIC_KEY>",  # Filled in by agent during key exchange
                "allowed_ips": params["remote_allowed_ips"],  # e.g. "10.200.0.2/32"
                "persistent_keepalive": params.get("persistent_keepalive", 25),
            },
            # MTU, DNS, etc
            "dns_servers": params.get("dns_servers", "1.1.1.1, 1.0.0.1"),
            "mtu": 1420,
        }