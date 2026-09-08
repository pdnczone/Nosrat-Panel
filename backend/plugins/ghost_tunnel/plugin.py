"""GhostTunnel (WireGuard + Cloak + Nginx) plugin for nosrat WebUI."""
from __future__ import annotations

import logging
import shlex
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


logger = logging.getLogger("nosrat.plugins.ghost_tunnel")


class GhostTunnelPlugin(Plugin):
    """Concrete plugin wrapping the GhostTunnel installer shipped at ``/ghost``."""

    name = "ghost_tunnel"
    display_name = "Ghost Tunnel"
    description = (
        "WireGuard running inside Cloak behind Nginx, with rotating URL paths. "
        "Designed to be invisible to DPI."
    )
    icon = "👻"

    # ── Wizard schema ─────────────────────────────────────────────────────

    def get_wizard_schema(self) -> dict[str, Any]:
        return {
            "step_1": {
                "title": "Domain",
                "description": "Optional custom domain pointing at this server.",
                "fields": [
                    {
                        "key": "use_domain",
                        "label": "Use a custom domain?",
                        "type": "boolean",
                        "default": False,
                        "required": True,
                    },
                    {
                        "key": "domain_name",
                        "label": "Domain (e.g. vpn.example.com)",
                        "type": "string",
                        "required": False,
                        "pattern": r"^(?=.{1,253}$)([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$",
                    },
                    {
                        "key": "email",
                        "label": "Let's Encrypt email",
                        "type": "string",
                        "format": "email",
                        "required": False,
                    },
                ],
            },
            "step_2": {
                "title": "VPN Users & DNS",
                "description": "How many VPN users and which DNS to advertise.",
                "fields": [
                    {
                        "key": "vpn_users",
                        "label": "Number of VPN users",
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 3,
                        "required": True,
                    },
                    {
                        "key": "dns_server",
                        "label": "Client DNS",
                        "type": "string",
                        "pattern": r"^(?:\d{1,3}\.){3}\d{1,3}$",
                        "default": "1.1.1.1",
                        "required": True,
                    },
                ],
            },
            "step_3": {
                "title": "Cloak",
                "description": "Obfuscation parameters.",
                "fields": [
                    {
                        "key": "cloak_redir",
                        "label": "Cloak redirect URL",
                        "type": "string",
                        "default": "www.bing.com",
                        "required": True,
                    },
                    {
                        "key": "path_rotation_hours",
                        "label": "Path rotation interval (hours)",
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 168,
                        "default": 6,
                        "required": True,
                    },
                ],
            },
        }

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def create(
        self, tunnel: Tunnel | None, local: Server, remote: Server, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Configure both endpoints for Ghost Tunnel mode."""
        cfg = self._build_ghost_config(tunnel, params)

        # Send config to both endpoints
        local_res, remote_res = await apply_tunnel_config(local, remote, self.name, cfg)

        return {
            "local": local_res,
            "remote": remote_res,
            "installer_staged_at": "/tmp/ghosttunnel-install",
            "preview": {
                "vpn_users": int(params.get("vpn_users", 3)),
                "dns_server": params.get("dns_server", "1.1.1.1"),
                "cloak_redir": params.get("cloak_redir", "www.bing.com"),
                "path_rotation_hours": int(params.get("path_rotation_hours", 6)),
            },
        }

    async def start(
        self, tunnel: Tunnel, local: Server, remote: Server
    ) -> dict[str, Any]:
        """Start all services on both endpoints."""
        services = ["wg-quick@wg0", "cloak-client", "nginx"]
        local_res, remote_res = await run_on_both_endpoints(
            local, remote, "start_services", [",".join(services)]
        )
        return {
            "local": local_res,
            "remote": remote_res,
            "status": "starting",
        }

    async def stop(
        self, tunnel: Tunnel, local: Server, remote: Server
    ) -> dict[str, Any]:
        """Stop all services on both endpoints."""
        services = ["wg-quick@wg0", "cloak-client", "nginx"]
        local_res, remote_res = await run_on_both_endpoints(
            local, remote, "stop_services", [",".join(services)]
        )
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
        local_res, remote_res = await run_on_both_endpoints(
            local, remote, "tunnel_status", [self.name]
        )
        return {
            "local": local_res,
            "remote": remote_res,
        }

    async def logs(
        self, tunnel: Tunnel, local: Server, remote: Server, *, lines: int = 100
    ) -> str:
        """Get recent Ghost Tunnel logs from both endpoints."""
        local_res, remote_res = await run_on_both_endpoints(
            local, remote, "journalctl",
            ["-u", "wg-quick@wg0", "-u", "cloak-client", "-u", "nginx", "-n", str(lines), "--no-pager", "-q"],
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

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _write_config(params: dict[str, Any]) -> Path:
        cfg_dir = Path("/etc/ghosttunnel")
        cfg_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        cfg_path = cfg_dir / "config.sh"

        body_lines: list[str] = [
            "#!/bin/bash",
            "# GhostTunnel configuration — written by nosrat WebUI",
            "",
            f'VPN_USERS={int(params.get("vpn_users", 3))}',
            f'CLOAK_REDIR={shlex.quote(str(params.get("cloak_redir", "www.bing.com")))}',
            f'DNS_SERVER={shlex.quote(str(params.get("dns_server", "1.1.1.1")))}',
            f'PATH_ROTATION_INTERVAL={int(params.get("path_rotation_hours", 6))}',
            "",
        ]
        cfg_path.write_text("\n".join(body_lines), encoding="utf-8")
        try:
            cfg_path.chmod(0o644)
        except OSError:  # pragma: no cover
            pass
        return cfg_path

    def _build_ghost_config(
        self, tunnel: Tunnel, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Build Ghost Tunnel configuration for the agent."""
        return {
            "plugin": self.name,
            "tunnel_id": tunnel.id,
            "tunnel_name": tunnel.name or f"ghost-{tunnel.id}",
            "vpn_users": int(params.get("vpn_users", 3)),
            "dns_server": params.get("dns_server", "1.1.1.1"),
            "cloak_redir": params.get("cloak_redir", "www.bing.com"),
            "path_rotation_hours": int(params.get("path_rotation_hours", 6)),
            "use_domain": params.get("use_domain", False),
            "domain_name": params.get("domain_name", ""),
            "email": params.get("email", ""),
        }