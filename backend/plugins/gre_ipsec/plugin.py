"""GRE-over-IPsec plugin for nosrat WebUI."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.config import settings
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

logger = logging.getLogger("nosrat.plugins.gre_ipsec")


class GreIpsecPlugin(Plugin):
    """Concrete plugin that wraps the GRE-over-IPsec tunnelling stack."""

    name = "gre_ipsec"
    display_name = "GRE-over-IPsec"
    description = (
        "Classic nosrat setup: GRE tunnel inside an IPsec transport-mode SA, "
        "suitable for Iran-side and external-server pairs."
    )
    icon = "🛡️"

    # ── Wizard schema ─────────────────────────────────────────────────────

    def get_wizard_schema(self) -> dict[str, Any]:
        return {
            "step_1": {
                "title": "Endpoint Selection",
                "description": "Choose which side of the tunnel this server is.",
                "fields": [
                    {
                        "key": "role",
                        "label": "Server Role",
                        "type": "string",
                        "enum": ["iran", "external"],
                        "default": "iran",
                        "required": True,
                        "ui:widget": "radio",
                    },
                ],
            },
            "step_2": {
                "title": "Endpoint IPs",
                "description": "Public IPv4 addresses for both ends.",
                "fields": [
                    {
                        "key": "local_public_ip",
                        "label": "Local Public IP",
                        "type": "string",
                        "pattern": r"^(?:\d{1,3}\.){3}\d{1,3}$",
                        "required": True,
                    },
                    {
                        "key": "remote_public_ip",
                        "label": "Remote Public IP",
                        "type": "string",
                        "pattern": r"^(?:\d{1,3}\.){3}\d{1,3}$",
                        "required": True,
                    },
                ],
            },
            "step_3": {
                "title": "GRE Addressing",
                "description": "Private /30 subnet used inside the GRE tunnel.",
                "fields": [
                    {
                        "key": "local_gre_ip",
                        "label": "Local GRE IP/CIDR",
                        "type": "string",
                        "default": "10.200.0.1/30",
                        "pattern": r"^\d+\.\d+\.\d+\.\d+/\d+$",
                        "required": True,
                    },
                    {
                        "key": "remote_gre_ip",
                        "label": "Remote GRE IP/CIDR",
                        "type": "string",
                        "default": "10.200.0.2/30",
                        "pattern": r"^\d+\.\d+\.\d+\.\d+/\d+$",
                        "required": True,
                    },
                ],
            },
            "step_4": {
                "title": "IPsec Parameters",
                "description": "Cryptographic settings for the IPsec SA.",
                "fields": [
                    {
                        "key": "encryption",
                        "label": "Encryption Algorithm",
                        "type": "string",
                        "enum": ["aes256gcm16", "aes128gcm16", "chacha20poly1305"],
                        "default": "aes256gcm16",
                        "required": True,
                        "ui:widget": "select",
                    },
                    {
                        "key": "dh_group",
                        "label": "Diffie-Hellman Group",
                        "type": "integer",
                        "enum": [14, 15, 16, 19, 20, 21],
                        "default": 14,
                        "required": True,
                        "ui:widget": "select",
                    },
                    {
                        "key": "rekey_seconds",
                        "label": "Rekey Interval (seconds)",
                        "type": "integer",
                        "minimum": 600,
                        "maximum": 86400,
                        "default": 3600,
                        "required": True,
                    },
                ],
            },
            "step_5": {
                "title": "PSK",
                "description": "Choose how to provision the Pre-Shared Key.",
                "fields": [
                    {
                        "key": "psk_mode",
                        "label": "PSK Mode",
                        "type": "string",
                        "enum": ["generate_256", "generate_512", "manual"],
                        "default": "generate_256",
                        "required": True,
                        "ui:widget": "radio",
                    },
                    {
                        "key": "psk_value",
                        "label": "Manual PSK (only if mode=manual)",
                        "type": "string",
                        "required": False,
                        "ui:widget": "password",
                    },
                ],
            },
        }

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def create(
        self, tunnel: Tunnel | None, local: Server, remote: Server, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Persist configuration on both endpoints via agent/SSH."""
        cfg = self._build_config(tunnel, local, remote, params)

        # Send config to both endpoints
        local_res, remote_res = await apply_tunnel_config(local, remote, self.name, cfg)

        return {
            "local": local_res,
            "remote": remote_res,
            "preview": {"written": True, "config": cfg},
        }

    async def start(
        self, tunnel: Tunnel, local: Server, remote: Server
    ) -> dict[str, Any]:
        """Start the tunnel on both endpoints."""
        local_res, remote_res = await start_tunnel(local, remote, self.name)
        return {
            "local": local_res,
            "remote": remote_res,
            "status": "starting",
        }

    async def stop(
        self, tunnel: Tunnel, local: Server, remote: Server
    ) -> dict[str, Any]:
        """Stop the tunnel on both endpoints."""
        local_res, remote_res = await stop_tunnel(local, remote, self.name)
        return {
            "local": local_res,
            "remote": remote_res,
            "status": "stopped",
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
        """Get status from both endpoints."""
        local_res, remote_res = await tunnel_status(local, remote, self.name)
        return {
            "local": local_res,
            "remote": remote_res,
        }

    async def logs(
        self, tunnel: Tunnel, local: Server, remote: Server, *, lines: int = 100
    ) -> str:
        """Fetch logs from both endpoints."""
        local_res, remote_res = await run_on_both_endpoints(
            local, remote, "journalctl", ["-u", "strongswan", "-u", "ipsec", "-n", str(lines), "--no-pager", "-q"]
        )
        return f"=== {local.name} ===\n{local_res.get('stdout', '')}\n\n=== {remote.name} ===\n{remote_res.get('stdout', '')}"

    async def destroy(
        self, tunnel: Tunnel, local: Server, remote: Server
    ) -> dict[str, Any]:
        """Remove all configuration on both endpoints."""
        local_res, remote_res = await run_on_both_endpoints(
            local, remote, "destroy_tunnel", [self.name]
        )
        return {
            "local": local_res,
            "remote": remote_res,
            "destroyed": True,
        }

    # ── Internal helpers ──────────────────────────────────────────────────

    def _build_config(
        self, tunnel: Tunnel, local: Server, remote: Server, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Build the full tunnel configuration dict for both endpoints."""
        import yaml

        # Determine which side is Iran vs External based on server role/location
        # The wizard 'role' param tells us which role THIS server has
        # But we need config for both sides
        local_is_iran = params.get("role") == "iran"

        if local_is_iran:
            iran_server = local
            external_server = remote
            iran_gre_ip = params["local_gre_ip"]
            external_gre_ip = params["remote_gre_ip"]
            iran_public = params["local_public_ip"]
            external_public = params["remote_public_ip"]
        else:
            iran_server = remote
            external_server = local
            iran_gre_ip = params["remote_gre_ip"]
            external_gre_ip = params["local_gre_ip"]
            iran_public = params["remote_public_ip"]
            external_public = params["local_public_ip"]

        # Generate PSK
        from core.security import generate_psk

        psk_mode = params.get("psk_mode", "generate_256")
        bits = 512 if psk_mode == "generate_512" else 256
        if psk_mode == "manual":
            psk = params.get("psk_value", "").strip()
            if not psk:
                raise ValueError("psk_value required when psk_mode=manual")
        else:
            psk = generate_psk(bits)

        # Build config for agent-side apply_tunnel_config handler
        return {
            "plugin": self.name,
            "tunnel_id": getattr(tunnel, "id", "temp"),
            "tunnel_name": getattr(tunnel, "name", f"gre-{params.get('role', 'unknown')}-init"),
            "psk": psk,
            "ipsec": {
                "encryption": params.get("encryption", "aes256gcm16"),
                "dh_group": int(params.get("dh_group", 14)),
                "rekey_seconds": int(params.get("rekey_seconds", 3600)),
            },
            "iran": {
                "server_id": iran_server.id,
                "public_ip": iran_public,
                "gre_ip": iran_gre_ip,
            },
            "external": {
                "server_id": external_server.id,
                "public_ip": external_public,
                "gre_ip": external_gre_ip,
            },
            "mtu": 1400,
            "keepalive": {"enabled": True, "interval": 10},
        }

    @staticmethod
    async def run_on_both_endpoints(
        local: Server, remote: Server, command: str, args: list[str], timeout: float = 30.0
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Helper to run a command on both endpoints."""
        from core.remote_exec import run_on_both_endpoints

        return await run_on_both_endpoints(local, remote, command, args, timeout=timeout)