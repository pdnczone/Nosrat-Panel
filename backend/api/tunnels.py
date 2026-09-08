"""Tunnel CRUD + lifecycle endpoints."""
from __future__ import annotations

import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user, record_audit
from core.plugin_loader import plugin_registry
from core.subprocess import CommandError, run
from db.models import Server, Tunnel, TunnelLog, User

logger = logging.getLogger("nosrat.api.tunnels")
router = APIRouter(prefix="/api/tunnels", tags=["tunnels"])


# ── Schemas ────────────────────────────────────────────────────────────────


class TunnelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    server_id: int | None
    plugin: str
    type: str
    name: str
    params: dict[str, Any]
    config_path: str | None
    status: str
    last_status_check: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class TunnelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128)
    plugin: str = Field(min_length=1, max_length=64)
    server_id: int | None = None
    local_server_id: int | None = None
    remote_server_id: int | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class TunnelUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = Field(default=None, min_length=1, max_length=128)
    params: dict[str, Any] | None = None
    server_id: int | None = None
    local_server_id: int | None = None
    remote_server_id: int | None = None


class TunnelActionResult(BaseModel):
    tunnel_id: int
    status: str
    detail: dict[str, Any] | None = None


class StatusReport(BaseModel):
    tunnel_id: int
    status: str
    detail: dict[str, Any]
    last_status_check: datetime


class RoutesReport(BaseModel):
    tunnel_id: int
    routes: list[dict[str, Any]]


class IpsecReport(BaseModel):
    tunnel_id: int
    associations: list[dict[str, Any]]
    policies: list[dict[str, Any]]


# ── Helpers ────────────────────────────────────────────────────────────────


def _ensure_plugin_loaded() -> None:
    plugin_registry.load()


def _get_plugin(name: str):
    try:
        return plugin_registry.get(name)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"plugin not found: {name}",
        ) from exc


def _resolve_servers(db: Session, tunnel: Tunnel) -> tuple[Server, Server] | None:
    """Resolve the local and remote Server objects for a tunnel.

    Uses ``local_server_id`` / ``remote_server_id`` if set, otherwise falls
    back to the legacy ``server_id`` (treated as ``local_server_id``).
    Returns ``None`` if servers cannot be resolved.
    """
    local_id = tunnel.local_server_id or tunnel.server_id
    remote_id = tunnel.remote_server_id

    if local_id is None or remote_id is None:
        return None

    local = db.get(Server, local_id)
    remote = db.get(Server, remote_id)
    if local is None or remote is None:
        return None

    return local, remote


def _log(db: Session, tunnel_id: int, message: str, *, level: str = "info") -> None:
    db.add(
        TunnelLog(
            tunnel_id=tunnel_id,
            level=level,
            message=message[:8192],
            timestamp=datetime.utcnow(),
        )
    )


# ── Routes ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[TunnelOut])
async def list_tunnels(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[TunnelOut]:
    tunnels = db.query(Tunnel).order_by(Tunnel.id.asc()).all()
    return [TunnelOut.model_validate(t) for t in tunnels]


@router.post("", response_model=TunnelOut, status_code=status.HTTP_201_CREATED)
async def create_tunnel(
    payload: TunnelCreate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TunnelOut:
    _ensure_plugin_loaded()
    if (
        db.query(Tunnel).filter(Tunnel.name == payload.name).first() is not None
    ):
        raise HTTPException(status_code=409, detail="tunnel name already exists")

    # Resolve servers
    local_server: Server | None = None
    remote_server: Server | None = None

    local_id = payload.local_server_id or payload.server_id
    remote_id = payload.remote_server_id

    if local_id:
        local_server = db.get(Server, local_id)
    if remote_id:
        remote_server = db.get(Server, remote_id)

    # If only server_id was given, set local_server_id for consistency
    if payload.server_id and not payload.local_server_id:
        payload.local_server_id = payload.server_id

    plugin = _get_plugin(payload.plugin)
    try:
        if local_server and remote_server:
            result = await plugin.create(
                None,  # tunnel not yet created in DB
                local_server,
                remote_server,
                payload.params,
            )
        else:
            # Fallback for single-server or demo mode
            result = await plugin.create(None, local_server or remote_server, remote_server or local_server or Server(name="demo", host="localhost", server_metadata={}), payload.params)
    except (ValueError, KeyError, CommandError) as exc:
        msg = str(exc)
        if isinstance(exc, KeyError):
            msg = f"missing required field: {exc.args[0]}"
        raise HTTPException(status_code=400, detail=msg) from exc

    tunnel = Tunnel(
        server_id=payload.server_id,
        local_server_id=payload.local_server_id,
        remote_server_id=payload.remote_server_id,
        plugin=payload.plugin,
        type=payload.plugin,
        name=payload.name,
        params=payload.params,
        config_path=(result or {}).get("config_path"),
        status="created",
    )
    db.add(tunnel)
    db.flush()
    _log(db, tunnel.id, f"tunnel created via plugin {payload.plugin}")
    record_audit(
        db,
        action="tunnel.create",
        user_id=user.id,
        target=tunnel.name,
        details={"plugin": tunnel.plugin, "server_id": tunnel.server_id},
        request=request,
    )
    db.commit()
    db.refresh(tunnel)
    return TunnelOut.model_validate(tunnel)


@router.get("/{tunnel_id}", response_model=TunnelOut)
async def get_tunnel(
    tunnel_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TunnelOut:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    return TunnelOut.model_validate(tunnel)


@router.put("/{tunnel_id}", response_model=TunnelOut)
async def update_tunnel(
    tunnel_id: int,
    payload: TunnelUpdate,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TunnelOut:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    if payload.name is not None and payload.name != tunnel.name:
        if db.query(Tunnel).filter(Tunnel.name == payload.name).first() is not None:
            raise HTTPException(status_code=409, detail="tunnel name already exists")
        tunnel.name = payload.name
    if payload.params is not None:
        tunnel.params = payload.params
    if payload.server_id is not None:
        tunnel.server_id = payload.server_id
    if payload.local_server_id is not None:
        tunnel.local_server_id = payload.local_server_id
    if payload.remote_server_id is not None:
        tunnel.remote_server_id = payload.remote_server_id
    record_audit(
        db,
        action="tunnel.update",
        user_id=user.id,
        target=tunnel.name,
        details=payload.model_dump(exclude_none=True),
        request=request,
    )
    db.commit()
    db.refresh(tunnel)
    return TunnelOut.model_validate(tunnel)


@router.delete("/{tunnel_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
async def delete_tunnel(
    tunnel_id: int,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    target = tunnel.name
    servers = _resolve_servers(db, tunnel)
    try:
        plugin = _get_plugin(tunnel.plugin)
        if servers:
            await plugin.destroy(tunnel, servers[0], servers[1])
        else:
            await plugin.destroy(tunnel, Server(name="demo", host="localhost", server_metadata={}), Server(name="demo", host="localhost", server_metadata={}))
    except (KeyError, CommandError) as exc:
        logger.warning("plugin destroy failed for %s: %s", tunnel.name, exc)
    db.delete(tunnel)
    record_audit(
        db,
        action="tunnel.delete",
        user_id=user.id,
        target=target,
        request=request,
    )
    db.commit()
    return None


# ── Lifecycle actions ─────────────────────────────────────────────────────


async def _lifecycle_action(
    tunnel: Tunnel,
    db: Session,
    action: str,
    plugin_method_name: str,
    error_status: str,
    success_status: str,
    request: Request,
    user: User,
) -> TunnelActionResult:
    """Generic lifecycle handler that resolves servers and dispatches to plugin."""
    plugin = _get_plugin(tunnel.plugin)
    servers = _resolve_servers(db, tunnel)
    try:
        if servers:
            result = await getattr(plugin, plugin_method_name)(tunnel, servers[0], servers[1])
        else:
            # Fallback for tunnels without two servers
            demo = Server(name="demo", host="localhost", server_metadata={})
            result = await getattr(plugin, plugin_method_name)(tunnel, demo, demo)
    except CommandError as exc:
        tunnel.status = "error"
        tunnel.error_message = exc.stderr or str(exc)
        _log(db, tunnel.id, f"{action} failed: {tunnel.error_message}", level="error")
        db.commit()
        raise HTTPException(status_code=500, detail=tunnel.error_message) from exc

    tunnel.status = (result or {}).get("status", success_status)
    tunnel.last_status_check = datetime.utcnow()
    if action != "start":
        tunnel.error_message = None
    _log(db, tunnel.id, f"tunnel {action}")
    record_audit(db, action=f"tunnel.{action}", user_id=user.id, target=tunnel.name, request=request)
    db.commit()
    return TunnelActionResult(tunnel_id=tunnel.id, status=tunnel.status, detail=result)


@router.post("/{tunnel_id}/start", response_model=TunnelActionResult)
async def start_tunnel_action(
    tunnel_id: int,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TunnelActionResult:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    return await _lifecycle_action(tunnel, db, "start", "start", "error", "starting", request, user)


@router.post("/{tunnel_id}/stop", response_model=TunnelActionResult)
async def stop_tunnel_action(
    tunnel_id: int,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TunnelActionResult:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    return await _lifecycle_action(tunnel, db, "stop", "stop", "error", "stopped", request, user)


@router.post("/{tunnel_id}/restart", response_model=TunnelActionResult)
async def restart_tunnel_action(
    tunnel_id: int,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TunnelActionResult:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    return await _lifecycle_action(tunnel, db, "restart", "restart", "error", "restarting", request, user)


# ── Inspection endpoints ──────────────────────────────────────────────────


@router.get("/{tunnel_id}/status", response_model=StatusReport)
async def tunnel_status(
    tunnel_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StatusReport:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    plugin = _get_plugin(tunnel.plugin)
    servers = _resolve_servers(db, tunnel)
    try:
        if servers:
            detail = await plugin.status(tunnel, servers[0], servers[1])
        else:
            demo = Server(name="demo", host="localhost", server_metadata={})
            detail = await plugin.status(tunnel, demo, demo)
    except CommandError as exc:
        detail = {"error": exc.stderr or str(exc), "returncode": exc.returncode}
    tunnel.last_status_check = datetime.utcnow()
    db.commit()
    return StatusReport(
        tunnel_id=tunnel.id,
        status=tunnel.status,
        detail=detail or {},
        last_status_check=tunnel.last_status_check,
    )


@router.get("/{tunnel_id}/logs")
async def tunnel_logs(
    tunnel_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    lines: int = 100,
    source: str = "plugin",
) -> dict[str, Any]:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")

    if source == "db":
        rows = (
            db.query(TunnelLog)
            .filter(TunnelLog.tunnel_id == tunnel.id)
            .order_by(TunnelLog.id.desc())
            .limit(min(max(lines, 1), 1000))
            .all()
        )
        entries = [
            {
                "id": r.id,
                "level": r.level,
                "message": r.message,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in reversed(rows)
        ]
        return {
            "tunnel_id": tunnel.id,
            "source": "db",
            "entries": entries,
            "lines": len(entries),
        }

    plugin = _get_plugin(tunnel.plugin)
    servers = _resolve_servers(db, tunnel)
    if servers:
        text = await plugin.logs(tunnel, servers[0], servers[1], lines=lines)
    else:
        demo = Server(name="demo", host="localhost", server_metadata={})
        text = await plugin.logs(tunnel, demo, demo, lines=lines)
    return {
        "tunnel_id": tunnel.id,
        "source": "plugin",
        "lines": lines,
        "text": text,
    }


@router.get("/{tunnel_id}/routes", response_model=RoutesReport)
async def tunnel_routes(
    tunnel_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RoutesReport:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")

    routes: list[dict[str, Any]] = []
    try:
        ip_out = await run(["ip", "-j", "route", "show"], timeout=5)
        for row in json.loads(ip_out.stdout or "[]"):
            routes.append(row)
    except (CommandError, ValueError) as exc:
        logger.warning("could not read ip route: %s", exc)

    return RoutesReport(tunnel_id=tunnel.id, routes=routes)


@router.get("/{tunnel_id}/ipsec", response_model=IpsecReport)
async def tunnel_ipsec(
    tunnel_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> IpsecReport:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")

    associations: list[dict[str, Any]] = []
    policies: list[dict[str, Any]] = []
    try:
        sa_out = await run(["ip", "-j", "xfrm", "state"], timeout=5)
        associations = json.loads(sa_out.stdout or "[]")
    except (CommandError, ValueError) as exc:
        logger.warning("could not read xfrm state: %s", exc)
    try:
        pol_out = await run(["ip", "-j", "xfrm", "policy"], timeout=5)
        policies = json.loads(pol_out.stdout or "[]")
    except (CommandError, ValueError) as exc:
        logger.warning("could not read xfrm policy: %s", exc)

    return IpsecReport(tunnel_id=tunnel.id, associations=associations, policies=policies)


@router.get("/{tunnel_id}/config")
async def tunnel_config(
    tunnel_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    if not tunnel.config_path:
        raise HTTPException(status_code=404, detail="no config path recorded")
    try:
        body = Path(tunnel.config_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"tunnel_id": tunnel.id, "path": tunnel.config_path, "body": body}


@router.get("/{tunnel_id}/qrcode")
async def tunnel_qrcode(
    tunnel_id: int,
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Render the tunnel definition as a scannable PNG QR code."""
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    try:
        import qrcode
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail="qrcode library is not installed (pip install 'qrcode[pil]')",
        ) from exc
    data = json.dumps(
        {
            "name": tunnel.name,
            "type": tunnel.type,
            "plugin": tunnel.plugin,
            "params": tunnel.params,
        },
        sort_keys=True,
    )
    buf = io.BytesIO()
    try:
        qrcode.make(data).save(buf, format="PNG")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"qrcode render failed: {exc}") from exc

    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="qr-{tunnel.name}.png"',
        },
    )