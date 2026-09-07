"""GRE-over-IPsec plugin for nosrat WebUI."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.config import settings
from core.subprocess import CommandError, run_nosrat
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

    async def create(self, params: dict[str, Any]) -> dict[str, Any]:
        cfg_path = self._config_path(params)
        cfg_path.parent.mkdir(parents=True, exist_ok=True)

        psk_path = self._write_psk(params)

        body = self._render_config(params, psk_path)
        cfg_path.write_text(body, encoding="utf-8")
        try:
            cfg_path.chmod(0o600)
        except OSError as exc:  # pragma: no cover
            logger.warning("could not chmod %s: %s", cfg_path, exc)

        return {
            "config_path": str(cfg_path),
            "psk_path": str(psk_path),
            "preview": {"written": True},
        }

    async def start(self, tunnel_id: int) -> dict[str, Any]:
        result = await run_nosrat(
            "start", timeout=settings.long_command_timeout_sec
        )
        if result.returncode != 0:
            raise CommandError(
                "failed to start GRE/IPsec tunnel",
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        return {"tunnel_id": tunnel_id, "status": "starting", "stdout": result.stdout}

    async def stop(self, tunnel_id: int) -> dict[str, Any]:
        result = await run_nosrat("stop")
        return {
            "tunnel_id": tunnel_id,
            "status": "stopping",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    async def restart(self, tunnel_id: int) -> dict[str, Any]:
        result = await run_nosrat(
            "restart", timeout=settings.long_command_timeout_sec
        )
        return {
            "tunnel_id": tunnel_id,
            "status": "restarting",
            "returncode": result.returncode,
            "stdout": result.stdout,
        }

    async def status(self, tunnel_id: int) -> dict[str, Any]:
        result = await run_nosrat("status")
        return {
            "tunnel_id": tunnel_id,
            "status": "unknown",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    async def logs(self, tunnel_id: int, *, lines: int = 100) -> str:
        from core.subprocess import run

        try:
            result = await run(
                [
                    "journalctl",
                    "-u",
                    "nosrat",
                    "-u",
                    "strongswan",
                    "-n",
                    str(max(1, min(lines, 1000))),
                    "--no-pager",
                    "-q",
                ],
                timeout=15,
            )
            return result.stdout or result.stderr
        except CommandError as exc:
            return exc.stderr or str(exc)

    async def destroy(self, tunnel_id: int) -> dict[str, Any]:
        from core.subprocess import run

        await run(["ip", "link", "del", "nosrat"], check=False)
        await run(["rm", "-f", settings.config_file, settings.psk_file], check=False)
        return {"tunnel_id": tunnel_id, "destroyed": True}

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _config_path(params: dict[str, Any]) -> Path:
        override = params.get("config_path")
        if override:
            return Path(override)
        return Path(settings.config_file)

    @staticmethod
    def _write_psk(params: dict[str, Any]) -> Path:
        mode = params.get("psk_mode", "generate_256")
        psk_path = Path(params.get("psk_path") or settings.psk_file)
        psk_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

        if mode == "manual":
            value = (params.get("psk_value") or "").strip()
            if not value:
                raise ValueError("psk_value required when psk_mode=manual")
            psk = value
        else:
            from core.security import generate_psk

            bits = 512 if mode == "generate_512" else 256
            psk = generate_psk(bits)

        psk_path.write_text(psk, encoding="utf-8")
        try:
            psk_path.chmod(0o600)
        except OSError:  # pragma: no cover
            pass
        return psk_path

    @staticmethod
    def _render_config(params: dict[str, Any], psk_path: Path) -> str:
        import yaml  # local import — only needed when actually writing

        cfg = {
            "tunnel": {"name": params.get("name", "nosrat")},
            "local": {
                "public_ip": params["local_public_ip"],
                "gre_ip": params["local_gre_ip"],
            },
            "remote": {
                "public_ip": params["remote_public_ip"],
                "gre_ip": params["remote_gre_ip"],
            },
            "ipsec": {
                "ike_version": 2,
                "mode": "transport",
                "encryption": params.get("encryption", "aes256gcm16"),
                "integrity": "",
                "dh_group": int(params.get("dh_group", 14)),
                "psk_file": str(psk_path),
                "rekey_seconds": int(params.get("rekey_seconds", 3600)),
                "dpd_delay": 10,
                "dpd_timeout": 30,
            },
            "routing": {"enabled": True, "static_routes": []},
            "firewall": {"enabled": True, "allow_ssh": True},
            "mtu": {"value": 1400, "mss_clamp": True},
            "keepalive": {"enabled": True, "interval": 10},
            "health": {
                "interval_seconds": 15,
                "latency_threshold_ms": 200,
                "loss_threshold_pct": 5,
                "auto_recover": True,
            },
            "failover": {
                "enabled": False,
                "secondary_public_ip": "",
                "switch_after_failures": 3,
            },
        }
        return yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)