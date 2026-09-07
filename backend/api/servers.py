"""Server (remote host) management endpoints."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user, record_audit
from core.subprocess import CommandError, run
from db.models import Server, User


logger = logging.getLogger("nosrat.api.servers")
router = APIRouter(prefix="/api/servers", tags=["servers"])


# ── Schemas ────────────────────────────────────────────────────────────────


class ServerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    host: str
    ssh_port: int
    ssh_user: str
    ssh_key_path: str | None
    status: str
    last_seen: datetime | None
    nosrat_version: str | None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ServerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9.\-_]+$")
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(default="root", min_length=1, max_length=64)
    ssh_key_path: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ServerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=128)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    ssh_user: str | None = Field(default=None, min_length=1, max_length=64)
    ssh_key_path: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] | None = None


class ServerTestResult(BaseModel):
    reachable: bool
    ssh_ok: bool
    nosrat_version: str | None
    latency_ms: float | None
    detail: str | None = None


# ── Routes ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[ServerOut])
async def list_servers(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ServerOut]:
    servers = db.query(Server).order_by(Server.id.asc()).all()
    return [ServerOut.model_validate(s) for s in servers]


@router.post("", response_model=ServerOut, status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: ServerCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ServerOut:
    if db.query(Server).filter(Server.name == payload.name).first():
        raise HTTPException(status_code=409, detail="server name already exists")
    server = Server(
        name=payload.name,
        host=payload.host,
        ssh_port=payload.ssh_port,
        ssh_user=payload.ssh_user,
        ssh_key_path=payload.ssh_key_path,
        status="unknown",
        server_metadata=payload.metadata,
    )
    db.add(server)
    db.flush()
    record_audit(
        db,
        action="server.create",
        user_id=user.id,
        target=server.name,
        details={"host": server.host, "ssh_port": server.ssh_port},
        request=request,
    )
    db.commit()
    db.refresh(server)
    return ServerOut.model_validate(server)


@router.get("/{server_id}", response_model=ServerOut)
async def get_server(
    server_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ServerOut:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")
    return ServerOut.model_validate(server)


@router.patch("/{server_id}", response_model=ServerOut)
async def update_server(
    server_id: int,
    payload: ServerUpdate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ServerOut:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")

    for field in ("name", "ssh_port", "ssh_user", "ssh_key_path"):
        value = getattr(payload, field)
        if value is not None:
            setattr(server, field, value)
    if payload.metadata is not None:
        server.server_metadata = payload.metadata

    record_audit(
        db,
        action="server.update",
        user_id=user.id,
        target=server.name,
        details=payload.model_dump(exclude_none=True),
        request=request,
    )
    db.commit()
    db.refresh(server)
    return ServerOut.model_validate(server)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: int,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")
    target = server.name
    db.delete(server)
    record_audit(
        db,
        action="server.delete",
        user_id=user.id,
        target=target,
        request=request,
    )
    db.commit()
    return None


@router.post("/{server_id}/test", response_model=ServerTestResult)
async def test_server(
    server_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ServerTestResult:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")

    ping_ok, latency_ms = await _ping(server.host)
    ssh_ok, ssh_detail = await _ssh_probe(server)
    version = await _nosrat_version(server) if ssh_ok else None

    server.status = (
        "online"
        if ping_ok and ssh_ok
        else ("unreachable" if not ping_ok else "ssh_failed")
    )
    server.last_seen = datetime.now(timezone.utc) if ping_ok else None
    server.nosrat_version = version
    db.commit()
    db.refresh(server)

    return ServerTestResult(
        reachable=ping_ok,
        ssh_ok=ssh_ok,
        nosrat_version=version,
        latency_ms=latency_ms,
        detail=None if ssh_ok else ssh_detail,
    )


# ── Helpers ────────────────────────────────────────────────────────────────


async def _ping(host: str, *, count: int = 3, deadline: int = 4) -> tuple[bool, float | None]:
    try:
        result = await run(
            ["ping", "-c", str(count), "-W", str(deadline), host],
            timeout=deadline * count + 5,
        )
    except CommandError:
        return False, None
    latency = _parse_ping_latency(result.stdout)
    return result.returncode == 0, latency


def _parse_ping_latency(output: str) -> float | None:
    for line in output.splitlines():
        if "rtt min/avg/max" in line or "round-trip" in line:
            try:
                stats = line.split("=")[1].split("/")
                return float(stats[1])
            except (IndexError, ValueError):
                continue
    return None


async def _ssh_probe(server: Server) -> tuple[bool, str | None]:
    ssh_args = [
        "ssh",
        "-p",
        str(server.ssh_port),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    if server.ssh_key_path:
        ssh_args.extend(["-i", server.ssh_key_path])
    ssh_args.extend([f"{server.ssh_user}@{server.host}", "true"])
    try:
        result = await run(ssh_args, timeout=10)
    except CommandError as exc:
        return False, exc.stderr or str(exc)
    return result.returncode == 0, result.stderr or None


async def _nosrat_version(server: Server) -> str | None:
    ssh_args = [
        "ssh",
        "-p",
        str(server.ssh_port),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    if server.ssh_key_path:
        ssh_args.extend(["-i", server.ssh_key_path])
    ssh_args.extend(
        [f"{server.ssh_user}@{server.host}", "nosrat version 2>/dev/null || echo unknown"]
    )
    try:
        result = await run(ssh_args, timeout=10)
    except CommandError:
        return None
    return result.stdout.strip() or None