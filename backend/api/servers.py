"""Server (remote host) management endpoints."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.database import get_db, session_scope
from core.deps import get_current_user, record_audit, require_admin
from core.ssh import SSHClient, SSHError
from core.metadata_crypto import encrypt_metadata, decrypt_metadata
from core.subprocess import CommandError, run
from db.models import NodeInstallJob, Server, User
from db.schemas import (
    NodeInstallLogChunk,
    NodeInstallRequest,
    NodeInstallResponse,
    ServerNodeOut,
)
from services import node_installer


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
    # ── Node agent state ─────────────────────────────────────────────
    node_installed: bool = False
    node_version: str | None = None
    node_name: str | None = None
    node_location: str | None = None
    node_status: str = "offline"
    node_last_seen: datetime | None = None


class ServerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128)
    host: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9.\-_]+$")
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(default="root", min_length=1, max_length=64)
    ssh_key_path: str | None = Field(default=None, max_length=512)
    ssh_private_key: str | None = Field(default=None, max_length=16384)
    ssh_password: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ServerUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = Field(default=None, min_length=1, max_length=128)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    ssh_user: str | None = Field(default=None, min_length=1, max_length=64)
    ssh_key_path: str | None = Field(default=None, max_length=512)
    node_name: str | None = Field(default=None, max_length=128)
    node_location: str | None = Field(default=None, max_length=32)


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
    meta = dict(payload.metadata or {})
    # Encrypt sensitive metadata fields before storing.
    if payload.ssh_private_key:
        meta["ssh_private_key"] = payload.ssh_private_key
    if payload.ssh_password:
        meta["ssh_password"] = payload.ssh_password
    meta = encrypt_metadata(meta)
    server = Server(
        name=payload.name,
        host=payload.host,
        ssh_port=payload.ssh_port,
        ssh_user=payload.ssh_user,
        ssh_key_path=payload.ssh_key_path,
        status="unknown",
        server_metadata=meta,
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

    meta = dict(server.server_metadata or {})
    private_key = getattr(payload, "ssh_private_key", None)
    password = getattr(payload, "ssh_password", None)
    new_metadata = getattr(payload, "metadata", None)
    if private_key:
        meta["ssh_private_key"] = private_key
    if password:
        meta["ssh_password"] = password
    meta = encrypt_metadata(meta)
    if new_metadata is not None:
        # Replace metadata only if the caller explicitly sent a dict; the
        # credentials above should still survive.
        for k, v in new_metadata.items():
            if k in ("ssh_private_key", "ssh_password"):
                continue
            meta[k] = v
    server.server_metadata = meta

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


@router.put("/{server_id}", response_model=ServerOut)
async def update_server_full(
    server_id: int,
    payload: ServerUpdate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ServerOut:
    """Full-update endpoint (PUT): apply only the fields the caller provided."""
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")
    for field in ("name", "host", "ssh_port", "ssh_user", "ssh_key_path", "node_name", "node_location"):
        value = getattr(payload, field)
        if value is not None:
            setattr(server, field, value)
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


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
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


# ── SSH connectivity test (asyncssh) ─────────────────────────────────────


class ServerSSHTest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str | None = Field(default=None, max_length=255)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    ssh_user: str | None = Field(default=None, max_length=64)
    ssh_key_path: str | None = Field(default=None, max_length=512)
    ssh_private_key: str | None = Field(default=None, max_length=16384)
    ssh_password: str | None = Field(default=None, max_length=512)


@router.post("/{server_id}/test-ssh", response_model=ServerTestResult)
async def test_ssh_connection(
    server_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    payload: ServerSSHTest | None = None,
) -> ServerTestResult:
    """Validate that the panel can open an asyncssh session to the server.

    Optional ``payload`` lets the caller supply fresh credentials without
    persisting them – useful for "Test before save" in the WebUI.
    """
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")

    creds = payload or ServerSSHTest()
    host = creds.host or server.host
    port = creds.ssh_port or server.ssh_port
    user = creds.ssh_user or server.ssh_user
    key_path = creds.ssh_key_path or server.ssh_key_path
    inline_key = creds.ssh_private_key
    password = creds.ssh_password or (server.server_metadata or {}).get("ssh_password")

    if not key_path and not inline_key and not password:
        meta = server.server_metadata or {}
        inline_key = meta.get("ssh_private_key")

    started = time.monotonic()
    try:
        async with SSHClient(
            host=host,
            port=port,
            username=user,
            private_key_path=key_path,
            private_key=inline_key,
            password=password,
            connect_timeout=10.0,
        ) as client:
            probe = await client.run_command("uname -a", timeout=10)
            latency_ms = (time.monotonic() - started) * 1000.0
            if not probe.ok:
                raise SSHError(f"uname failed: {probe.stderr}")
            return ServerTestResult(
                reachable=True,
                ssh_ok=True,
                nosrat_version=server.nosrat_version,
                latency_ms=round(latency_ms, 2),
                detail=None,
            )
    except SSHError as exc:
        return ServerTestResult(
            reachable=False,
            ssh_ok=False,
            nosrat_version=None,
            latency_ms=None,
            detail=str(exc),
        )


# ── Node install endpoints ───────────────────────────────────────────────


@router.post(
    "/{server_id}/install-node",
    response_model=NodeInstallResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def install_node(
    server_id: int,
    payload: NodeInstallRequest,
    request: Request,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> NodeInstallResponse:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")
    try:
        job = node_installer.start_install(
            server_id,
            node_name=payload.node_name,
            location=payload.location,
            force=payload.force,
            initiated_by=user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_audit(
        db,
        action="server.install_node",
        user_id=user.id,
        target=server.name,
        details={"job_id": job.id, "force": payload.force},
        request=request,
    )
    db.commit()
    return NodeInstallResponse(
        job_id=job.id,
        server_id=server.id,
        status=job.status,
        progress=job.progress,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
        package_manager=job.package_manager,
    )


@router.get("/{server_id}/install-status", response_model=NodeInstallLogChunk)
async def install_status(
    server_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    after_line: int = Query(default=0, ge=0, description="resume after this many log lines"),
) -> NodeInstallLogChunk:
    job = (
        db.query(NodeInstallJob)
        .filter(NodeInstallJob.server_id == server_id)
        .order_by(NodeInstallJob.id.desc())
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="no install job for this server")
    log = job.log or ""
    lines = log.splitlines()
    tail = "\n".join(lines[after_line:])
    return NodeInstallLogChunk(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        tail=tail,
        error=job.error,
    )


@router.get("/{server_id}/node-info", response_model=ServerNodeOut)
async def node_info(
    server_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ServerNodeOut:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")
    return ServerNodeOut.model_validate(server)


# ── SSH terminal WebSocket ───────────────────────────────────────────────


@router.websocket("/{server_id}/terminal")
async def ssh_terminal(
    websocket: WebSocket,
    server_id: int,
    cols: int = Query(default=80, ge=8, le=400),
    rows: int = Query(default=24, ge=2, le=200),
    token: str | None = Query(default=None),
) -> None:
    """Open an interactive SSH shell to the server and proxy I/O over WS.

    Frames from the browser (``text`` -> ``stdin``, ``binary`` -> ``Ctrl``
    sequences) are forwarded to the SSH process; output is streamed back
    as text frames.
    """
    # Authn: token query param OR Authorization header (set up by api.js)
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        from core.security import decode_token

        decode_token(token)
    except Exception:  # noqa: BLE001
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    with session_scope() as db:
        server = db.get(Server, server_id)
        if server is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="server not found")
            return
        meta = server.server_metadata or {}
        creds = {
            "host": server.host,
            "port": server.ssh_port,
            "username": server.ssh_user,
            "key_path": server.ssh_key_path,
            "inline_key": meta.get("ssh_private_key"),
            "password": meta.get("ssh_password"),
        }

    ssh = SSHClient(
        host=creds["host"],
        port=creds["port"],
        username=creds["username"],
        private_key_path=creds["key_path"],
        private_key=creds["inline_key"],
        password=creds["password"],
        connect_timeout=15.0,
    )
    try:
        await ssh.connect()
    except SSHError as exc:
        await websocket.send_text(f"\r\n\x1b[31mssh connect failed: {exc}\x1b[0m\r\n")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    try:
        async with ssh.stream_command(
            "bash -l",
            term_type="xterm-256color",
            term_size=(rows, cols, 0, 0),
        ) as proc:
            await websocket.send_text(
                f"\x1b[2mconnected to {creds['username']}@{creds['host']}\x1b[0m\r\n"
            )

            async def _ws_to_ssh() -> None:
                while True:
                    msg = await websocket.receive()
                    if msg.get("type") == "websocket.disconnect":
                        return
                    data = msg.get("text") or msg.get("bytes")
                    if data is None:
                        continue
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", errors="replace")
                    if data.startswith("\x1b[8;{0};{1}t".format(rows, cols)):
                        continue  # resize handled separately
                    if data.startswith("RESIZE:"):
                        try:
                            _, payload = data.split(":", 1)
                            new_rows, new_cols = payload.split("x", 1)
                            proc.change_term_size(int(new_rows), int(new_cols), 0, 0)
                        except Exception:  # noqa: BLE001
                            pass
                        continue
                    if proc.stdin is None or proc.stdin.is_closing():
                        return
                    try:
                        proc.stdin.write(data)
                        await proc.stdin.drain()
                    except (ConnectionError, BrokenPipeError):
                        return

            async def _ssh_to_ws() -> None:
                assert proc.stdout is not None
                while True:
                    buf = await proc.stdout.read(4096)
                    if not buf:
                        break
                    text = buf.decode("utf-8", errors="replace")
                    try:
                        await websocket.send_text(text)
                    except Exception:  # noqa: BLE001
                        return

            sender = asyncio.create_task(_ws_to_ssh())
            receiver = asyncio.create_task(_ssh_to_ws())
            done, pending = await asyncio.wait(
                {sender, receiver},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
    except WebSocketDisconnect:
        return
    except SSHError as exc:
        try:
            await websocket.send_text(f"\r\n\x1b[31mssh error: {exc}\x1b[0m\r\n")
        except Exception:  # noqa: BLE001
            pass
    finally:
        await ssh.disconnect()


# ── Local imports kept at bottom to avoid circulars ───────────────────────
import time  # noqa: E402  (used by test_ssh_connection)