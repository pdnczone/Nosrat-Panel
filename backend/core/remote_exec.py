"""Remote execution helpers — dispatch commands to servers via agent bus (preferred)
or SSH fallback. Used by plugins to run tunnel lifecycle operations on the actual
endpoint servers, not on the panel host.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from core.agent_bus import bus
from core.ssh import SSHClient
from core.ssh_utils import resolve_ssh_credentials
from db.models import Server

logger = logging.getLogger("nosrat.remote_exec")

# Message types the node-agent understands (see node-agent/agent.py).
TUNNEL_MSG_TYPES = {
    "apply_tunnel_config",
    "start_tunnel",
    "stop_tunnel",
    "tunnel_status",
    "destroy_tunnel",
}


async def run_on_server(
    server: Server,
    command: str,
    args: list[str] | None = None,
    *,
    timeout: float = 60.0,
    expect_json: bool = False,
) -> dict[str, Any]:
    """Execute a command on ``server``.

    Priority:
    1. If the server has an online node-agent, use the agent bus. For tunnel
       lifecycle commands (apply_tunnel_config/start_tunnel/stop_tunnel/
       tunnel_status/destroy_tunnel) the dedicated WS message type is used;
       anything else goes through the generic ``command`` type.
    2. Otherwise fall back to SSH.

    Returns a dict with at least ``stdout``, ``stderr``, ``exit_code``.
    If ``expect_json=True`` and agent returns JSON in ``stdout``, the parsed
    JSON is returned under key ``data``.
    """
    if bus.is_online(server.id):
        if command in TUNNEL_MSG_TYPES:
            return await _dispatch_tunnel_msg(server, command, args or [], timeout)
        return await _run_via_agent(server, command, args, timeout, expect_json)
    return await _run_via_ssh(server, command, args, timeout)


async def _dispatch_tunnel_msg(
    server: Server, mtype: str, args: list[str], timeout: float
) -> dict[str, Any]:
    """Dispatch a dedicated tunnel-lifecycle message to the agent.

    ``args`` is a list in the form ``[plugin_name, config_json, tunnel_id]``
    where config_json is optional.
    """
    plugin = args[0] if args else ""
    config_raw = args[1] if len(args) > 1 else None
    tunnel_id = args[2] if len(args) > 2 else 0

    try:
        config = json.loads(config_raw) if isinstance(config_raw, str) else (config_raw or {})
    except json.JSONDecodeError:
        config = {}

    cmd_id = uuid.uuid4().hex[:12]
    payload: dict[str, Any] = {"plugin": plugin}
    if config:
        payload["config"] = config
    if tunnel_id:
        payload["tunnel_id"] = int(tunnel_id)

    try:
        reply = await bus.request(
            server.id,
            {"type": mtype, "id": cmd_id, "payload": payload},
            expect_reply="command_result",
            timeout=timeout + 5,
        )
        if reply is None:
            raise RuntimeError(f"agent did not reply for {mtype}")
        return {
            "stdout": reply.get("payload", {}).get("stdout", ""),
            "stderr": reply.get("payload", {}).get("stderr", ""),
            "exit_code": reply.get("payload", {}).get("exit_code", -1),
            "data": reply.get("payload", {}),
        }
    except asyncio.TimeoutError:
        logger.warning("agent %s timeout server_id=%s", mtype, server.id)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent %s failed server_id=%s: %s", mtype, server.id, exc)
        # Fall back to SSH running the host-side equivalent (mirror of agent logic)
        return await _run_via_ssh(server, _ssh_equivalent(mtype, plugin), None, timeout)


def _ssh_equivalent(mtype: str, plugin: str) -> str:
    """Build a shell command approximating the agent handler for SSH fallback."""
    if mtype == "start_tunnel":
        if plugin == "gre_ipsec":
            return (
                "systemctl start strongswan 2>/dev/null || systemctl start ipsec 2>/dev/null; "
                "ip link set gre0 up 2>/dev/null; true"
            )
        if plugin == "wireguard_native":
            return "true"  # wg-quick up handled by caller naming
        return "systemctl start wg-quick@wg0 cloak-client nginx 2>/dev/null; true"
    if mtype == "stop_tunnel":
        if plugin == "gre_ipsec":
            return (
                "ip link set gre0 down 2>/dev/null; ip link del gre0 2>/dev/null; "
                "systemctl stop strongswan 2>/dev/null || systemctl stop ipsec 2>/dev/null; true"
            )
        if plugin == "wireguard_native":
            return "true"
        return "systemctl stop wg-quick@wg0 cloak-client nginx 2>/dev/null; true"
    if mtype == "tunnel_status":
        if plugin == "gre_ipsec":
            return "ip link show gre0 2>/dev/null && echo GRE_UP || echo GRE_DOWN"
        if plugin == "wireguard_native":
            return "true"
        return "systemctl is-active wg-quick@wg0 cloak-client nginx 2>/dev/null"
    if mtype == "destroy_tunnel":
        return "rm -rf /etc/nosrat-tunnels && true"
    if mtype == "apply_tunnel_config":
        return "mkdir -p /etc/nosrat-tunnels && true"
    return "true"


async def _run_via_agent(
    server: Server,
    command: str,
    args: list[str] | None,
    timeout: float,
    expect_json: bool,
) -> dict[str, Any]:
    """Dispatch via node-agent generic ``command`` message type."""
    cmd_id = uuid.uuid4().hex[:12]
    payload = {
        "type": "command",
        "id": cmd_id,
        "payload": {
            "command": command,
            "args": args or [],
            "timeout": int(timeout),
        },
    }

    try:
        reply = await bus.request(
            server.id,
            payload,
            expect_reply="command_result",
            timeout=timeout + 5,
        )
        if reply is None:
            raise RuntimeError("agent did not reply in time")

        result = reply.get("payload", {})
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        exit_code = result.get("exit_code", -1)

        data = None
        if expect_json and stdout.strip():
            try:
                data = json.loads(stdout.strip())
            except json.JSONDecodeError:
                data = None

        return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code, "data": data}
    except asyncio.TimeoutError:
        logger.warning("agent command timeout server_id=%s cmd=%s", server.id, command)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("agent command failed server_id=%s: %s", server.id, exc)
        return await _run_via_ssh(server, command, args, timeout)


async def _run_via_ssh(
    server: Server,
    command: str,
    args: list[str] | None,
    timeout: float,
) -> dict[str, Any]:
    """Execute via SSH using stored credentials."""
    creds = resolve_ssh_credentials(server)
    if not creds:
        raise RuntimeError(f"No SSH credentials configured for server {server.name}")

    host = server.host
    port = server.ssh_port or 22
    user = server.ssh_user or "root"

    client = SSHClient(
        host, port, user,
        password=creds.get("password"),
        private_key=creds.get("private_key"),
    )
    try:
        await client.connect()
        full_cmd = command
        if args:
            full_cmd = " ".join([command] + [f'"{a}"' if " " in a else a for a in args])
        result = await client.run(full_cmd, timeout=timeout)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "data": None,
        }
    finally:
        await client.close()


async def run_on_both_endpoints(
    local: Server,
    remote: Server,
    command: str,
    args: list[str] | None = None,
    *,
    timeout: float = 60.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the same command on both endpoints concurrently.

    Returns (local_result, remote_result).
    """
    local_task = asyncio.create_task(run_on_server(local, command, args, timeout=timeout))
    remote_task = asyncio.create_task(run_on_server(remote, command, args, timeout=timeout))
    return await asyncio.gather(local_task, remote_task)


async def apply_tunnel_config(
    local: Server,
    remote: Server,
    plugin_name: str,
    config: dict[str, Any],
    *,
    timeout: float = 120.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Ask both endpoints to write the plugin's config and prepare the tunnel."""
    return await run_on_both_endpoints(
        local,
        remote,
        "apply_tunnel_config",
        [plugin_name, json.dumps(config), str(config.get("tunnel_id", 0))],
        timeout=timeout,
    )


async def start_tunnel(
    local: Server,
    remote: Server,
    plugin_name: str,
    tunnel_id: int = 0,
    *,
    timeout: float = 60.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Start the tunnel on both endpoints."""
    return await run_on_both_endpoints(
        local, remote, "start_tunnel", [plugin_name, "", str(tunnel_id)], timeout=timeout
    )


async def stop_tunnel(
    local: Server,
    remote: Server,
    plugin_name: str,
    tunnel_id: int = 0,
    *,
    timeout: float = 60.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Stop the tunnel on both endpoints."""
    return await run_on_both_endpoints(
        local, remote, "stop_tunnel", [plugin_name, "", str(tunnel_id)], timeout=timeout
    )


async def tunnel_status(
    local: Server,
    remote: Server,
    plugin_name: str,
    tunnel_id: int = 0,
    *,
    timeout: float = 30.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Get status from both endpoints."""
    return await run_on_both_endpoints(
        local, remote, "tunnel_status", [plugin_name, "", str(tunnel_id)], timeout=timeout
    )


async def destroy_tunnel(
    local: Server,
    remote: Server,
    plugin_name: str,
    tunnel_id: int = 0,
    *,
    timeout: float = 60.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Destroy tunnel config on both endpoints."""
    return await run_on_both_endpoints(
        local, remote, "destroy_tunnel", [plugin_name, "", str(tunnel_id)], timeout=timeout
    )