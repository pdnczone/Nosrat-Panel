"""HTTP endpoints for managing ``nosrat-node`` agents.

The agent-facing WebSocket lives in ``ws.py`` (``/ws/agent``).  This
module is for the dashboard's REST needs:

* listing currently-registered nodes and their status,
* fetching metric history,
* dispatching commands,
* reading streamed logs.
"""
from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.agent_bus import bus
from core.database import get_db, session_scope
from core.deps import get_current_user, record_audit
from db.models import NodeCommand, NodeLog, NodeMetric, Server, User
from db.schemas import (
    NodeCommandOut,
    NodeCommandRequest,
    NodeLogOut,
    NodeMetricIn,
    NodeMetricOut,
)


logger = logging.getLogger("nosrat.api.nodes")
router = APIRouter(prefix="/api/nodes", tags=["nodes"])


# ── Request/Response helpers ──────────────────────────────────────────────


class NodeListEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    server_id: int
    server_name: str
    host: str
    node_name: str | None = None
    node_location: str | None = None
    node_version: str | None = None
    node_status: str
    node_installed: bool
    node_last_seen: datetime | None = None
    online: bool
    uptime_seconds: int | None = None


class NodeCommandAck(BaseModel):
    command_id: str
    status: str
    queued: bool
    accepted_at: datetime


class NodeMetricsQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    since_minutes: int = Field(default=60, ge=1, le=7 * 24 * 60)
    limit: int = Field(default=500, ge=1, le=5000)


# ── Routes ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[NodeListEntry])
async def list_nodes(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[NodeListEntry]:
    """Return every server that has a node token configured (installed or not)."""
    servers = db.query(Server).order_by(Server.id.asc()).all()
    online_ids = set(bus.online_servers())
    out: list[NodeListEntry] = []
    for s in servers:
        online = s.id in online_ids
        uptime = None
        conn = bus.get(s.id)
        if online and conn is not None:
            uptime = int(time.time() - conn.connected_at)
        out.append(
            NodeListEntry(
                server_id=s.id,
                server_name=s.name,
                host=s.host,
                node_name=s.node_name,
                node_location=s.node_location,
                node_version=s.node_version,
                node_status="online" if online else (s.node_status or "offline"),
                node_installed=s.node_installed,
                node_last_seen=s.node_last_seen,
                online=online,
                uptime_seconds=uptime,
            )
        )
    return out


class NodeRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server_id: int | None = Field(default=None, description="Existing server ID to attach to")
    name: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9.\-_]+$")
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(default="root", min_length=1, max_length=64)
    node_name: str | None = Field(default=None, max_length=128)
    node_location: str | None = Field(default=None, max_length=32)


@router.post("", response_model=NodeListEntry, status_code=status.HTTP_201_CREATED)
async def register_node(
    payload: NodeRegisterRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NodeListEntry:
    """Manually register a node agent (generates a node token for the agent to connect with)."""
    from core.agent_auth import issue_node_token

    if payload.server_id:
        server = db.get(Server, payload.server_id)
        if server is None:
            raise HTTPException(status_code=404, detail="server not found")
    else:
        if db.query(Server).filter(Server.name == payload.name).first():
            raise HTTPException(status_code=409, detail="server name already exists")
        server = Server(
            name=payload.name,
            host=payload.host,
            ssh_port=payload.ssh_port,
            ssh_user=payload.ssh_user,
            status="unknown",
            server_metadata={},
        )
        db.add(server)
        db.flush()

    server.node_name = payload.node_name or payload.name
    server.node_location = payload.node_location or "external"
    # Manual registration does NOT verify the node is installed. Keep
    # node_installed=False (not yet verified) and node_status="pending"
    # until the agent actually connects via /ws/agent (mark_registered
    # flips node_installed=True + node_status="online"). This prevents a
    # node that was never installed from being reported as installed.

    token = issue_node_token(
        server.id,
        node_name=server.node_name or payload.name,
        location=server.node_location or "external",
    )
    server.node_token = token
    server.node_status = "pending"
    server.node_installed = False

    record_audit(
        db,
        action="node.register_manual",
        user_id=user.id,
        target=server.name,
        details={"host": server.host},
        request=request,
    )
    db.commit()
    db.refresh(server)

    online = bus.is_online(server.id)
    return NodeListEntry(
        server_id=server.id,
        server_name=server.name,
        host=server.host,
        node_name=server.node_name,
        node_location=server.node_location,
        node_version=server.node_version,
        node_status="pending",
        node_installed=False,
        node_last_seen=server.node_last_seen,
        online=online,
        uptime_seconds=None,
    )


@router.get("/{server_id}", response_model=NodeListEntry)
async def get_node(
    server_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NodeListEntry:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")
    online = bus.is_online(server_id)
    uptime = None
    conn = bus.get(server_id)
    if online and conn is not None:
        uptime = int(time.time() - conn.connected_at)
    return NodeListEntry(
        server_id=server.id,
        server_name=server.name,
        host=server.host,
        node_name=server.node_name,
        node_location=server.node_location,
        node_version=server.node_version,
        node_status="online" if online else (server.node_status or "offline"),
        node_installed=server.node_installed,
        node_last_seen=server.node_last_seen,
        online=online,
        uptime_seconds=uptime,
    )


@router.post(
    "/{server_id}/command",
    response_model=NodeCommandAck,
    status_code=status.HTTP_202_ACCEPTED,
)
async def dispatch_command(
    server_id: int,
    payload: NodeCommandRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NodeCommandAck:
    """Push a command to a node agent and persist a pending audit record.

    Returns 202 immediately; the result lands later via ``GET /commands/{id}``
    once the agent answers with a ``command_result`` message.
    """
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")
    if not server.node_installed:
        raise HTTPException(status_code=409, detail="node not installed on this server")

    command_id = secrets.token_hex(12)
    now = datetime.now(timezone.utc)

    record = NodeCommand(
        server_id=server.id,
        command_id=command_id,
        command=payload.command,
        args=payload.args,
        issued_by=user.id,
        issued_at=now,
        status="pending",
    )
    db.add(record)
    db.flush()
    record_audit(
        db,
        action="node.command",
        user_id=user.id,
        target=server.name,
        details={"command": payload.command, "command_id": command_id},
        request=request,
    )
    db.commit()

    queued = await bus.send(
        server_id,
        {
            "type": "command",
            "id": command_id,
            "payload": {
                "command": payload.command,
                "args": payload.args,
                "timeout": payload.timeout,
            },
        },
        timeout=5.0,
    )
    if not queued:
        record.status = "failed"
        record.error = "agent offline"
        db.commit()
        raise HTTPException(status_code=503, detail="node agent offline")

    return NodeCommandAck(
        command_id=command_id, status="pending", queued=True, accepted_at=now
    )


@router.get("/{server_id}/metrics", response_model=list[NodeMetricOut])
async def metrics_history(
    server_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    since_minutes: int = Query(default=60, ge=1, le=7 * 24 * 60),
    limit: int = Query(default=500, ge=1, le=5000),
) -> list[NodeMetricOut]:
    if db.get(Server, server_id) is None:
        raise HTTPException(status_code=404, detail="server not found")
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
    rows = (
        db.query(NodeMetric)
        .filter(NodeMetric.server_id == server_id, NodeMetric.timestamp >= cutoff)
        .order_by(NodeMetric.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [NodeMetricOut.model_validate(r) for r in rows]


@router.get("/{server_id}/metrics/latest", response_model=NodeMetricOut | None)
async def latest_metric(
    server_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NodeMetricOut | None:
    row = (
        db.query(NodeMetric)
        .filter(NodeMetric.server_id == server_id)
        .order_by(NodeMetric.timestamp.desc())
        .first()
    )
    return NodeMetricOut.model_validate(row) if row else None


@router.get("/{server_id}/logs", response_model=list[NodeLogOut])
async def list_logs(
    server_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    since_minutes: int = Query(default=30, ge=1, le=24 * 60),
    limit: int = Query(default=200, ge=1, le=2000),
) -> list[NodeLogOut]:
    if db.get(Server, server_id) is None:
        raise HTTPException(status_code=404, detail="server not found")
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
    rows = (
        db.query(NodeLog)
        .filter(NodeLog.server_id == server_id, NodeLog.timestamp >= cutoff)
        .order_by(NodeLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [NodeLogOut.model_validate(r) for r in rows]


@router.get("/{server_id}/commands", response_model=list[NodeCommandOut])
async def list_commands(
    server_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=500),
) -> list[NodeCommandOut]:
    if db.get(Server, server_id) is None:
        raise HTTPException(status_code=404, detail="server not found")
    rows = (
        db.query(NodeCommand)
        .filter(NodeCommand.server_id == server_id)
        .order_by(NodeCommand.issued_at.desc())
        .limit(limit)
        .all()
    )
    return [NodeCommandOut.model_validate(r) for r in rows]


# ── Agent → panel ingestion helpers (called from /ws/agent) ───────────────


def record_metric(server_id: int, payload: NodeMetricIn) -> NodeMetric:
    with session_scope() as db:
        server = db.get(Server, server_id)
        if server is None:
            raise LookupError(f"server {server_id} not found")
        row = NodeMetric(
            server_id=server_id,
            timestamp=payload.timestamp or datetime.now(timezone.utc),
            cpu_percent=payload.cpu_percent,
            ram_percent=payload.ram_percent,
            ram_used_mb=payload.ram_used_mb,
            ram_total_mb=payload.ram_total_mb,
            disk_percent=payload.disk_percent,
            disk_used_gb=payload.disk_used_gb,
            network_rx_bytes=payload.network_rx_bytes,
            network_tx_bytes=payload.network_tx_bytes,
            load_avg_1m=payload.load_avg_1m,
            load_avg_5m=payload.load_avg_5m,
            load_avg_15m=payload.load_avg_15m,
            uptime_seconds=payload.uptime_seconds,
            hostname=payload.hostname,
            extra=payload.extra,
        )
        db.add(row)
        server.node_last_seen = datetime.now(timezone.utc)
        server.node_status = "online"
        db.flush()
        return row


def record_log(server_id: int, level: str, source: str, message: str) -> NodeLog:
    with session_scope() as db:
        row = NodeLog(
            server_id=server_id,
            level=level,
            source=source,
            message=message,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(row)
        db.flush()
        return row


def complete_command(
    server_id: int,
    *,
    command_id: str,
    status: str,
    stdout: str | None,
    stderr: str | None,
    exit_code: int | None,
) -> NodeCommand | None:
    with session_scope() as db:
        row = (
            db.query(NodeCommand)
            .filter(
                NodeCommand.server_id == server_id,
                NodeCommand.command_id == command_id,
            )
            .first()
        )
        if row is None:
            logger.warning("unknown command_id=%s server=%s", command_id, server_id)
            return None
        row.status = status
        row.stdout = stdout
        row.stderr = stderr
        row.exit_code = exit_code
        row.completed_at = datetime.now(timezone.utc)
        return row


def mark_registered(server_id: int, *, hostname: str, version: str, location: str | None) -> None:
    with session_scope() as db:
        server = db.get(Server, server_id)
        if server is None:
            return
        server.node_status = "online"
        server.node_last_seen = datetime.now(timezone.utc)
        server.node_version = version
        if location:
            server.node_location = location
        if hostname and not server.node_name:
            server.node_name = hostname
        server.node_installed = True