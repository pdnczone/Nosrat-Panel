"""Tunnel CRUD + lifecycle endpoints."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user, record_audit
from core.plugin_loader import plugin_registry
from core.subprocess import CommandError, run
from db.models import Tunnel, TunnelLog, User


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
    params: dict[str, Any] = Field(default_factory=dict)


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

    plugin = _get_plugin(payload.plugin)
    try:
        result = await plugin.create(payload.params)
    except (ValueError, CommandError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tunnel = Tunnel(
        server_id=payload.server_id,
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


@router.delete("/{tunnel_id}", status_code=status.HTTP_204_NO_CONTENT)
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
    try:
        plugin = _get_plugin(tunnel.plugin)
        await plugin.destroy(tunnel.id)
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


@router.post("/{tunnel_id}/start", response_model=TunnelActionResult)
async def start_tunnel(
    tunnel_id: int,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TunnelActionResult:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    plugin = _get_plugin(tunnel.plugin)
    try:
        result = await plugin.start(tunnel.id)
    except CommandError as exc:
        tunnel.status = "error"
        tunnel.error_message = exc.stderr or str(exc)
        _log(db, tunnel.id, f"start failed: {tunnel.error_message}", level="error")
        db.commit()
        raise HTTPException(status_code=500, detail=tunnel.error_message) from exc
    tunnel.status = (result or {}).get("status", "starting")
    tunnel.last_status_check = datetime.utcnow()
    tunnel.error_message = None
    _log(db, tunnel.id, "tunnel started")
    record_audit(
        db, action="tunnel.start", user_id=user.id, target=tunnel.name, request=request
    )
    db.commit()
    return TunnelActionResult(tunnel_id=tunnel.id, status=tunnel.status, detail=result)


@router.post("/{tunnel_id}/stop", response_model=TunnelActionResult)
async def stop_tunnel(
    tunnel_id: int,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TunnelActionResult:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    plugin = _get_plugin(tunnel.plugin)
    try:
        result = await plugin.stop(tunnel.id)
    except CommandError as exc:
        _log(db, tunnel.id, f"stop failed: {exc.stderr or exc}", level="error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    tunnel.status = (result or {}).get("status", "stopped")
    tunnel.last_status_check = datetime.utcnow()
    _log(db, tunnel.id, "tunnel stopped")
    record_audit(
        db, action="tunnel.stop", user_id=user.id, target=tunnel.name, request=request
    )
    db.commit()
    return TunnelActionResult(tunnel_id=tunnel.id, status=tunnel.status, detail=result)


@router.post("/{tunnel_id}/restart", response_model=TunnelActionResult)
async def restart_tunnel(
    tunnel_id: int,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TunnelActionResult:
    tunnel = db.get(Tunnel, tunnel_id)
    if tunnel is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    plugin = _get_plugin(tunnel.plugin)
    try:
        result = await plugin.restart(tunnel.id)
    except CommandError as exc:
        tunnel.status = "error"
        tunnel.error_message = exc.stderr or str(exc)
        _log(db, tunnel.id, f"restart failed: {tunnel.error_message}", level="error")
        db.commit()
        raise HTTPException(status_code=500, detail=tunnel.error_message) from exc
    tunnel.status = (result or {}).get("status", "restarting")
    tunnel.last_status_check = datetime.utcnow()
    tunnel.error_message = None
    _log(db, tunnel.id, "tunnel restarted")
    record_audit(
        db, action="tunnel.restart", user_id=user.id, target=tunnel.name, request=request
    )
    db.commit()
    return TunnelActionResult(tunnel_id=tunnel.id, status=tunnel.status, detail=result)


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
    try:
        detail = await plugin.status(tunnel.id)
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
    text = await plugin.logs(tunnel.id, lines=lines)
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