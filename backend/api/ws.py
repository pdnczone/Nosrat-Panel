"""WebSocket endpoints for live status, log streaming and node agents."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt

from api.nodes import complete_command, mark_registered, record_log, record_metric
from core.agent_auth import AgentAuthError, decode_node_token, has_scope
from core.deps import get_current_user
from core.agent_bus import bus, parse_payload, safe_send_json
from core.config import settings
from core.plugin_loader import plugin_registry
from core.subprocess import run
from core.database import SessionLocal
from db.schemas import (
    NodeCommandResultIn,
    NodeLogIn,
    NodeMetricIn,
    NodeRegisterIn,
)


logger = logging.getLogger("nosrat.api.ws")
router = APIRouter(tags=["websocket"])


# ── Connection helpers ────────────────────────────────────────────────────


async def _authenticate_ws(websocket: WebSocket) -> dict[str, Any] | None:
    """Validate the JWT supplied via ``?token=`` query parameter or header."""
    token: str | None = websocket.query_params.get("token")
    if not token:
        token = websocket.query_params.get("token")
    if not token:
        auth = websocket.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        logger.warning("websocket auth failed: %s", exc)
        return None


# ── /ws/status ──────────────────────────────────────────────────────────────


def _decode_ws_token(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


async def _status_loop(websocket: WebSocket, interval: int) -> None:
    await websocket.accept()
    plugin_registry.load()
    last_ping = time.monotonic()
    try:
        while True:
            snapshot = await _collect_snapshot()
            await websocket.send_json(snapshot)

            now = time.monotonic()
            if now - last_ping > settings.ws_heartbeat_sec:
                await websocket.send_json({"type": "heartbeat", "ts": now})
                last_ping = now

            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("ws status error: %s", exc)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:  # noqa: BLE001
            pass


@router.websocket("/ws/status")
async def status_socket(
    websocket: WebSocket,
    interval: int = Query(default=2, ge=1, le=30),
    token: str | None = Query(default=None),
) -> None:
    """Stream status snapshots of all tunnels at the requested cadence."""
    claims = _decode_ws_token(token)
    if claims is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await _status_loop(websocket, interval)


@router.websocket("/ws/events")
async def events_socket(
    websocket: WebSocket,
    interval: int = Query(default=2, ge=1, le=30),
    token: str | None = Query(default=None),
) -> None:
    """Alias of ``/ws/status`` — identical tunnel status snapshot stream."""
    claims = _decode_ws_token(token)
    if claims is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await _status_loop(websocket, interval)


async def _collect_snapshot() -> dict[str, Any]:
    """Collect a single status snapshot from all tunnels."""
    plugin_registry.load()
    tunnels: list[dict[str, Any]] = []
    with SessionLocal() as db:
        from db.models import Tunnel

        for tunnel in db.query(Tunnel).order_by(Tunnel.id.asc()).all():
            try:
                plugin = plugin_registry.get(tunnel.plugin)
                detail = await plugin.status(tunnel.id)
            except (KeyError, Exception) as exc:  # noqa: BLE001
                detail = {"error": str(exc)}
            tunnels.append(
                {
                    "id": tunnel.id,
                    "name": tunnel.name,
                    "plugin": tunnel.plugin,
                    "status": tunnel.status,
                    "last_status_check": tunnel.last_status_check.isoformat()
                    if tunnel.last_status_check
                    else None,
                    "detail": detail,
                }
            )
    return {"type": "status_snapshot", "ts": time.time(), "tunnels": tunnels}


# ── /ws/logs/:tunnel_id ────────────────────────────────────────────────────


@router.websocket("/ws/logs/{tunnel_id}")
async def logs_socket(
    websocket: WebSocket,
    tunnel_id: int,
    lines: int = Query(default=100, ge=1, le=1000),
    follow: bool = Query(default=False),
    token: str | None = Query(default=None),
) -> None:
    """Stream tunnel logs.  Sends the tail first, then optionally follows journald."""
    claims = None
    if token:
        try:
            claims = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        except JWTError:
            claims = None
    if claims is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    with SessionLocal() as db:
        from db.models import Tunnel

        tunnel = db.get(Tunnel, tunnel_id)
        if tunnel is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="tunnel not found")
            return
        plugin_id = tunnel.plugin

    await websocket.accept()
    plugin_registry.load()

    try:
        plugin = plugin_registry.get(plugin_id)
        history = await plugin.logs(tunnel_id, lines=lines)
        for chunk in _chunk_lines(history):
            await websocket.send_json({"type": "log", "message": chunk})

        if not follow:
            await websocket.send_json({"type": "eof"})
            return

        # Follow journald tail -n 0 -f for the most recent activity.
        proc = await asyncio.create_subprocess_exec(
            "journalctl",
            "-u",
            "nosrat",
            "-u",
            "strongswan",
            "-n",
            "0",
            "-f",
            "--no-pager",
            "-q",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            assert proc.stdout is not None
            while True:
                buf = await proc.stdout.readline()
                if not buf:
                    break
                await websocket.send_json(
                    {"type": "log", "message": buf.decode(errors="replace").rstrip()}
                )
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()

    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("ws logs error: %s", exc)
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)


def _chunk_lines(text: str, *, size: int = 256) -> list[str]:
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]


# ── /ws/agent ────────────────────────────────────────────────────────────


@router.websocket("/ws/agent")
async def agent_socket(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """Persistent WebSocket used by ``nosrat-node`` agents.

    Auth: ``?token=<node-jwt>`` (see ``core.agent_auth``).

    Messages from agent -> panel:

    * ``{"type": "register", "payload": NodeRegisterIn}``
    * ``{"type": "metrics",  "payload": NodeMetricIn}``
    * ``{"type": "log",      "payload": NodeLogIn}``
    * ``{"type": "command_result", "id": "...", "payload": NodeCommandResultIn}``
    * ``{"type": "pong"}``

    Messages from panel -> agent:

    * ``{"type": "command", "id": "...", "payload": {...}}``
    * ``{"type": "ping"}``
    * ``{"type": "update",  "payload": {"version": "..."}}``
    """
    if not token:
        token = websocket.query_params.get("token")
    if not token:
        auth = websocket.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="missing token")
        return

    try:
        claims = decode_node_token(token)
    except AgentAuthError as exc:
        logger.warning("agent auth failed: %s", exc)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc))
        return

    server_id_raw = claims.get("server_id")
    if server_id_raw is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="missing server_id")
        return
    try:
        server_id = int(server_id_raw)
    except (TypeError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="invalid server_id")
        return
    if not has_scope(claims, f"server:{server_id}"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="scope mismatch")
        return

    await websocket.accept()
    conn = await bus.register(server_id, websocket)
    conn.node_name = claims.get("node_name")
    conn.location = claims.get("location")

    logger.info(
        "agent ws opened server_id=%s node=%s location=%s",
        server_id,
        conn.node_name,
        conn.location,
    )

    # Heartbeat task
    heartbeat_task: asyncio.Task[None] | None = None
    stop_event = asyncio.Event()

    async def _heartbeat() -> None:
        try:
            while not stop_event.is_set():
                await asyncio.sleep(settings.ws_heartbeat_sec)
                if not await safe_send_json(websocket, {"type": "ping", "ts": time.time()}):
                    break
        except asyncio.CancelledError:
            return

    try:
        heartbeat_task = asyncio.create_task(_heartbeat())

        while True:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            raw = msg.get("text") or msg.get("bytes") or b""
            data = parse_payload(raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace"))
            if data is None:
                continue
            bus.touch(server_id)
            mtype = data.get("type")
            mid = data.get("id")
            payload = data.get("payload") or {}

            if mtype == "register":
                try:
                    reg = NodeRegisterIn.model_validate(payload)
                    conn.hostname = reg.hostname
                    conn.version = reg.version
                    mark_registered(
                        server_id,
                        hostname=reg.hostname,
                        version=reg.version,
                        location=reg.location or conn.location,
                    )
                    await safe_send_json(
                        websocket,
                        {
                            "type": "registered",
                            "id": mid,
                            "payload": {"server_id": server_id, "ok": True},
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("register parse failed")
                    await safe_send_json(
                        websocket,
                        {"type": "error", "id": mid, "payload": {"error": str(exc)}},
                    )
                continue

            if mtype == "metrics":
                try:
                    metric = NodeMetricIn.model_validate(payload)
                    record_metric(server_id, metric)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("metrics parse failed: %s", exc)
                continue

            if mtype == "log":
                try:
                    entry = NodeLogIn.model_validate(payload)
                    record_log(server_id, entry.level, entry.source, entry.message)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("log parse failed: %s", exc)
                continue

            if mtype == "command_result":
                try:
                    result = NodeCommandResultIn.model_validate({"command_id": mid, **payload})
                    complete_command(
                        server_id,
                        command_id=result.command_id,
                        status=result.status,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        exit_code=result.exit_code,
                    )
                    bus.resolve_command(server_id, "command_result", data)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("command_result failed: %s", exc)
                continue

            if mtype == "pong":
                continue

            # Unrecognised message — log and ignore.
            logger.debug("agent ws: unknown type=%r", mtype)

    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent ws error server=%s: %s", server_id, exc)
    finally:
        stop_event.set()
        if heartbeat_task:
            heartbeat_task.cancel()
        await bus.unregister(server_id, websocket)


# ── /api/nodes/ws (operator-facing fan-out of agent events) ───────────────


@router.websocket("/api/nodes/ws")
async def node_events_socket(websocket: WebSocket) -> None:
    """Operator channel that mirrors agent activity as Svelte store events.

    The frontend opens ``/api/nodes/ws`` to receive real-time updates
    (metrics, logs, command results) without having to subscribe to a
    specific node first.
    """
    token = websocket.query_params.get("token")
    if not token:
        auth = websocket.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if claims.get("type") != "access":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept()
    # Lightweight polling fan-out; in production swap for pubsub.
    last_sent: dict[int, float] = {}
    try:
        while True:
            snapshot = bus.snapshot()
            await websocket.send_json({"type": "node_snapshot", "ts": time.time(), "nodes": snapshot})
            await asyncio.sleep(2.0)
            last_sent[0] = time.time()
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        logger.debug("node events ws closed: %s", exc)