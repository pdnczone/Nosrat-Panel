"""Periodic per-client usage accounting + quota/expiry enforcement.

This is separate from ``core/deps.py`` (which guards panel operator
accounts). ``TunnelClient`` rows are VPN subscribers with a data quota and
an expiry window. A background job samples real traffic from the underlying
tunnel (WireGuard ``wg show transfer``, GRE/IPsec stats where available),
updates ``used_bytes``, and disables clients that exceed quota or reach the
expiry date.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from core.database import session_scope
from core.plugin_loader import plugin_registry
from db.models import Tunnel, TunnelClient, UsageSample

logger = logging.getLogger("nosrat.usage")

USAGE_INTERVAL_SEC = int(__import__("os").getenv("NOSRAT_USAGE_INTERVAL_SEC", "300"))


async def _read_tunnel_traffic(tunnel: Tunnel) -> dict[str, int] | None:
    """Return {rx, tx, total} bytes for a tunnel, or None if unavailable.

    Delegates to the plugin's ``status()`` if it returns byte counts
    (WireGuard native). Returns None when no plugin can report traffic.
    """
    try:
        plugin = plugin_registry.get(tunnel.plugin)
    except Exception:  # noqa: BLE001
        return None
    if plugin is None:
        return None
    try:
        status = await plugin.status(tunnel.id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("usage plugin status failed for tunnel %s: %s", tunnel.id, exc)
        return None
    if not isinstance(status, dict):
        return None
    rx = status.get("traffic_in_bytes")
    tx = status.get("traffic_out_bytes")
    total = status.get("traffic_total_bytes")
    if rx is None and tx is None and total is None:
        return None
    rx = int(rx or 0)
    tx = int(tx or 0)
    if total is None:
        total = rx + tx
    return {"rx": rx, "tx": tx, "total": int(total)}


def _enforce_client(client: TunnelClient, traffic: dict[str, int] | None) -> None:
    """Update used_bytes and flip a client to disabled when over quota/expired."""
    now = datetime.now(timezone.utc)

    if client.expires_at is not None and client.expires_at <= now:
        client.status = "expired"
        client.note = f"expired at {client.expires_at.isoformat()}"
        return

    if traffic is not None:
        client.used_bytes = traffic["total"]

    if client.quota_bytes > 0 and client.used_bytes >= client.quota_bytes:
        if client.status != "over_quota":
            client.status = "over_quota"
            client.note = f"quota reached ({client.used_bytes}/{client.quota_bytes} bytes)"
        # TODO: issue the actual tunnel disable via plugin.stop() once a
        # per-peer mechanism exists. For now enforcement is recorded at the
        # client level and surfaced in the UI + API.


async def run_usage_cycle() -> None:
    """One pass over all clients: sample traffic, enforce quota/expiry."""
    with session_scope() as db:
        clients = db.query(TunnelClient).all()
        if not clients:
            return
        tunnel_cache: dict[int, Tunnel] = {}
        for client in clients:
            traffic: dict[str, int] | None = None
            if client.tunnel_id in tunnel_cache:
                traffic = tunnel_cache[client.tunnel_id]
            elif client.tunnel_id is not None:
                tunnel = db.get(Tunnel, client.tunnel_id)
                if tunnel is not None:
                    traffic = await _read_tunnel_traffic(tunnel)
                tunnel_cache[client.tunnel_id] = traffic  # type: ignore[assignment]
            _enforce_client(client, traffic)
        db.commit()


async def usage_loop() -> None:
    """Background: sample usage every ``USAGE_INTERVAL_SEC`` seconds."""
    logger.info("usage loop started (interval=%ss)", USAGE_INTERVAL_SEC)
    while True:
        try:
            await run_usage_cycle()
        except Exception as exc:  # noqa: BLE001
            logger.warning("usage cycle error: %s", exc)
        await asyncio.sleep(USAGE_INTERVAL_SEC)
