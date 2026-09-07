"""In-process registry of live node-agent WebSocket connections.

A node opens a single WebSocket back to ``/ws/agent`` after registering. The
panel keeps the connection here so that:

* the dashboard can show which nodes are online,
* commands / updates can be pushed without round-trip polling,
* log fan-out works for multiple operators subscribed to the same node.

The registry is intentionally in-process: a single FastAPI worker is
sufficient for the panel size described in the task.  In a multi-worker
deployment it can be swapped for Redis pubsub – the public API stays the
same.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


logger = logging.getLogger("nosrat.agent_bus")


MessageHandler = Callable[[int, dict[str, Any]], Awaitable[None] | None]


@dataclass(slots=True)
class NodeConnection:
    server_id: int
    websocket: WebSocket
    connected_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    node_name: str | None = None
    hostname: str | None = None
    version: str | None = None
    location: str | None = None
    pending_commands: dict[str, asyncio.Future[dict[str, Any]]] = field(default_factory=dict)


class AgentBus:
    """Singleton registry of ``NodeConnection``s."""

    def __init__(self) -> None:
        self._by_server: dict[int, NodeConnection] = {}
        self._lock = asyncio.Lock()

    # ── Connection lifecycle ───────────────────────────────────────────

    async def register(self, server_id: int, websocket: WebSocket) -> NodeConnection:
        async with self._lock:
            existing = self._by_server.get(server_id)
            if existing is not None:
                logger.info("replacing existing agent connection server_id=%s", server_id)
                try:
                    await existing.websocket.close(code=1000)
                except Exception:  # noqa: BLE001
                    pass
            conn = NodeConnection(server_id=server_id, websocket=websocket)
            self._by_server[server_id] = conn
            logger.info("agent connected server_id=%s", server_id)
            return conn

    async def unregister(self, server_id: int, websocket: WebSocket | None = None) -> None:
        async with self._lock:
            conn = self._by_server.get(server_id)
            if conn is None:
                return
            if websocket is not None and conn.websocket is not websocket:
                return  # a newer connection has taken over
            del self._by_server[server_id]
            for fut in conn.pending_commands.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("agent disconnected"))
            logger.info("agent disconnected server_id=%s", server_id)

    def is_online(self, server_id: int) -> bool:
        return server_id in self._by_server

    def online_servers(self) -> list[int]:
        return list(self._by_server.keys())

    def get(self, server_id: int) -> NodeConnection | None:
        return self._by_server.get(server_id)

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "server_id": c.server_id,
                "node_name": c.node_name,
                "hostname": c.hostname,
                "version": c.version,
                "location": c.location,
                "connected_at": c.connected_at,
                "last_seen": c.last_seen,
                "online_for": time.time() - c.connected_at,
                "idle_for": time.time() - c.last_seen,
            }
            for c in self._by_server.values()
        ]

    # ── Messaging ──────────────────────────────────────────────────────

    async def send(
        self, server_id: int, message: dict[str, Any], *, timeout: float = 10.0
    ) -> bool:
        """Send ``message`` to the agent.  Returns ``False`` if offline."""
        conn = self._by_server.get(server_id)
        if conn is None:
            return False
        try:
            await asyncio.wait_for(conn.websocket.send_json(message), timeout=timeout)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("send failed server_id=%s: %s", server_id, exc)
            await self.unregister(server_id, conn.websocket)
            return False

    async def request(
        self,
        server_id: int,
        message: dict[str, Any],
        *,
        expect_reply: str,
        timeout: float = 60.0,
    ) -> dict[str, Any] | None:
        """Send ``message`` and wait for a reply whose ``type`` is ``expect_reply``."""
        conn = self._by_server.get(server_id)
        if conn is None:
            return None
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        conn.pending_commands[expect_reply] = fut
        try:
            ok = await self.send(server_id, message, timeout=timeout)
            if not ok:
                return None
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            conn.pending_commands.pop(expect_reply, None)

    def resolve_command(self, server_id: int, reply_type: str, message: dict[str, Any]) -> bool:
        """Resolve a future waiting on ``reply_type`` for ``server_id``."""
        conn = self._by_server.get(server_id)
        if conn is None:
            return False
        fut = conn.pending_commands.get(reply_type)
        if fut is None or fut.done():
            return False
        fut.set_result(message)
        return True

    def touch(self, server_id: int) -> None:
        conn = self._by_server.get(server_id)
        if conn is not None:
            conn.last_seen = time.time()


bus = AgentBus()


# ── Helpers for route handlers ───────────────────────────────────────────


async def safe_send_json(websocket: WebSocket, payload: dict[str, Any]) -> bool:
    """Send JSON without raising – used in handlers that may be cancelled."""
    try:
        await websocket.send_json(payload)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("send_json failed: %s", exc)
        return False


def parse_payload(raw: str | bytes) -> dict[str, Any] | None:
    """Tolerantly parse an agent message.  Returns ``None`` on garbage."""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data