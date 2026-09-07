"""GhostTunnel (WireGuard + Cloak + Nginx) plugin for nosrat WebUI."""
from __future__ import annotations

import logging
import shlex
from pathlib import Path
from typing import Any

from core.subprocess import CommandError, run, run_shell
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

    async def create(self, params: dict[str, Any]) -> dict[str, Any]:
        cfg_path = self._write_config(params)

        return {
            "config_path": str(cfg_path),
            "preview": {
                "vpn_users": int(params.get("vpn_users", 3)),
                "dns_server": params.get("dns_server", "1.1.1.1"),
                "cloak_redir": params.get("cloak_redir", "www.bing.com"),
                "path_rotation_hours": int(params.get("path_rotation_hours", 6)),
            },
            "installer_staged_at": "/tmp/ghosttunnel-install",
        }

    async def start(self, tunnel_id: int) -> dict[str, Any]:
        for unit in ("wg-quick@wg0", "cloak", "nginx"):
            try:
                await run(["systemctl", "start", unit], check=False)
            except CommandError as exc:
                logger.warning("failed to start %s: %s", unit, exc)
        return {"tunnel_id": tunnel_id, "status": "starting"}

    async def stop(self, tunnel_id: int) -> dict[str, Any]:
        for unit in ("wg-quick@wg0", "cloak", "nginx"):
            try:
                await run(["systemctl", "stop", unit], check=False)
            except CommandError as exc:
                logger.warning("failed to stop %s: %s", unit, exc)
        return {"tunnel_id": tunnel_id, "status": "stopped"}

    async def restart(self, tunnel_id: int) -> dict[str, Any]:
        for unit in ("wg-quick@wg0", "cloak", "nginx"):
            try:
                await run(["systemctl", "restart", unit], check=False)
            except CommandError as exc:
                logger.warning("failed to restart %s: %s", unit, exc)
        return {"tunnel_id": tunnel_id, "status": "restarted"}

    async def status(self, tunnel_id: int) -> dict[str, Any]:
        result: dict[str, Any] = {"tunnel_id": tunnel_id, "units": {}}
        for unit in ("wg-quick@wg0", "cloak", "nginx"):
            try:
                r = await run(
                    ["systemctl", "is-active", unit],
                    timeout=5,
                    check=False,
                )
                result["units"][unit] = {
                    "active": r.stdout.strip() == "active",
                    "raw": r.stdout.strip(),
                }
            except CommandError as exc:
                result["units"][unit] = {"active": False, "error": str(exc)}
        try:
            r = await run_shell("cat /var/www/html/current-path 2>/dev/null || true")
            result["current_path"] = r.stdout.strip()
        except CommandError:
            result["current_path"] = None
        return result

    async def logs(self, tunnel_id: int, *, lines: int = 100) -> str:
        n = max(1, min(lines, 1000))
        try:
            result = await run(
                [
                    "journalctl",
                    "-u",
                    "wg-quick@wg0",
                    "-u",
                    "cloak",
                    "-u",
                    "nginx",
                    "-n",
                    str(n),
                    "--no-pager",
                    "-q",
                ],
                timeout=15,
            )
            return result.stdout or result.stderr
        except CommandError as exc:
            return exc.stderr or str(exc)

    async def destroy(self, tunnel_id: int) -> dict[str, Any]:
        cfg_path = Path("/etc/ghost_tunnel/config.sh")
        if cfg_path.exists():
            cfg_path.unlink(missing_ok=True)
        await run_shell(
            "rm -rf /etc/wireguard/clients /var/www/html/current-path",
            check=False,
        )
        return {"tunnel_id": tunnel_id, "destroyed": True}

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