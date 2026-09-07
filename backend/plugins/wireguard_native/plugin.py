"""WireGuard native plugin - simple wg-quick wrapper.

Example plugin showing how to integrate a new tunnel type
with the nosrat-panel plugin system.
"""
from typing import Any
from pathlib import Path
import json
import subprocess

from plugins.base import Plugin


class WireGuardNativePlugin(Plugin):
    """
    Manages a native WireGuard tunnel using wg-quick.

    This is a minimal example plugin for the nosrat-panel system.
    """

    # ── Required Plugin class attributes ─────────────────────────────────
    name = "wireguard_native"
    display_name = "WireGuard (Native)"
    description = "Native WireGuard tunnel without obfuscation - simple and fast"
    icon = "🔌"

    def get_wizard_schema(self) -> dict[str, Any]:
        """Load and return the wizard form schema."""
        schema_path = Path(__file__).parent / "wizard_schema.json"
        with open(schema_path) as f:
            return json.load(f)

    def _get_config_path(self, tunnel_id: int) -> Path:
        return Path(f"/etc/wireguard/wg{tunnel_id}.conf")

    def _generate_keypair(self) -> tuple[str, str]:
        """Generate a new WireGuard keypair."""
        private = subprocess.run(
            ["wg", "genkey"], capture_output=True, text=True, check=True
        ).stdout.strip()
        public = subprocess.run(
            ["wg", "pubkey"], input=private, capture_output=True, text=True, check=True
        ).stdout.strip()
        return private, public

    async def create(self, params: dict[str, Any]) -> dict[str, Any]:
        """Create a new WireGuard interface configuration."""
        tunnel_id = params.get("_tunnel_id", 0)
        config_path = self._get_config_path(tunnel_id)

        # Generate keypair
        private_key, public_key = self._generate_keypair()

        # Build config
        config = f"""[Interface]
Address = {params['client_address']}
PrivateKey = {private_key}
DNS = {params.get('dns_servers', '1.1.1.1, 1.0.0.1')}

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = {params['server_endpoint']}:{params['server_port']}
AllowedIPs = {params['allowed_ips']}
PersistentKeepalive = {params.get('persistent_keepalive', 25)}
"""

        # Write config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config)
        config_path.chmod(0o600)

        return {
            "config_path": str(config_path),
            "status": "created",
            "public_key": public_key,
            "message": f"WireGuard config created. Public key: {public_key}",
        }

    async def start(self, tunnel_id: int) -> dict[str, Any]:
        """Bring up the WireGuard interface."""
        interface = f"wg{tunnel_id}"
        result = subprocess.run(
            ["wg-quick", "up", interface],
            capture_output=True, text=True,
        )
        return {
            "success": result.returncode == 0,
            "message": result.stdout if result.returncode == 0 else result.stderr,
        }

    async def stop(self, tunnel_id: int) -> dict[str, Any]:
        """Bring down the WireGuard interface."""
        interface = f"wg{tunnel_id}"
        result = subprocess.run(
            ["wg-quick", "down", interface],
            capture_output=True, text=True,
        )
        return {
            "success": result.returncode == 0,
            "message": result.stdout if result.returncode == 0 else result.stderr,
        }

    async def restart(self, tunnel_id: int) -> dict[str, Any]:
        """Restart the tunnel."""
        await self.stop(tunnel_id)
        return await self.start(tunnel_id)

    async def status(self, tunnel_id: int) -> dict[str, Any]:
        """Get WireGuard interface status and stats."""
        interface = f"wg{tunnel_id}"
        result = subprocess.run(
            ["wg", "show", interface],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return {
                "status": "inactive",
                "error_message": result.stderr,
            }

        # Parse `wg show` output for transfer stats
        transfer_rx = 0
        transfer_tx = 0
        for line in result.stdout.splitlines():
            if "transfer:" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "received,":
                        transfer_rx = self._parse_bytes(parts[i - 1])
                    elif part == "sent":
                        transfer_tx = self._parse_bytes(parts[i - 1])

        return {
            "status": "active",
            "traffic_in_bytes": transfer_rx,
            "traffic_out_bytes": transfer_tx,
        }

    async def logs(self, tunnel_id: int, *, lines: int = 100) -> str:
        """Get recent WireGuard logs."""
        interface = f"wg{tunnel_id}"
        result = subprocess.run(
            ["journalctl", "-u", f"wg-quick@{interface}", "-n", str(lines), "--no-pager"],
            capture_output=True, text=True,
        )
        return result.stdout

    async def destroy(self, tunnel_id: int) -> dict[str, Any]:
        """Remove the WireGuard configuration."""
        await self.stop(tunnel_id)
        config_path = self._get_config_path(tunnel_id)
        if config_path.exists():
            config_path.unlink()
        return {"success": True, "message": "Configuration removed"}

    @staticmethod
    def _parse_bytes(size_str: str) -> int:
        """Parse a size string like '1.23 MiB' to bytes."""
        units = {
            "B": 1,
            "KiB": 1024,
            "MiB": 1024 ** 2,
            "GiB": 1024 ** 3,
            "TiB": 1024 ** 4,
        }
        parts = size_str.split()
        if len(parts) != 2:
            return 0
        try:
            value = float(parts[0])
            unit = parts[1]
            return int(value * units.get(unit, 1))
        except (ValueError, KeyError):
            return 0
