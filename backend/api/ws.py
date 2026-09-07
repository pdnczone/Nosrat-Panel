"""WebSocket endpoints for live status and log streaming."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt

from core.config import settings
from core.deps import get_current_user
from core.plugin_loader import plugin_registry
from core.subprocess import run
from db.database import SessionLocal


logger = logging.getLogger("nosrat.api.ws")
router = APIRouter(tags=["websocket"])


# ── Connection helpers ────────────────────────────────────────────────────


async def _authenticate_ws(websocket: WebSocket) -> dict[str, Any] | None:
    """Validate the JWT supplied via ``?token=`` query parameter or header."""
    token: str | None = websocket.query_params.get("token")
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


@router.websocket("/ws/status")
async def status_socket(
    websocket: WebSocket,
    interval: int = Query(default=2, ge=1, le=30),
    token: str | None = Query(default=None),
) -> None:
    """Stream status snapshots of all tunnels at the requested cadence."""
    claims = None
    if token:
        try:
            claims = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        except JWTError:
            claims = None
    if claims is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

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
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)


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