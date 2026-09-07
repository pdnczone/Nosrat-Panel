"""Dashboard statistics + recent activity endpoints."""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user
from db.models import AuditLog, NodeMetric, Server, SpeedTestResult, Tunnel, User


logger = logging.getLogger("nosrat.api.stats")
router = APIRouter(prefix="/api/stats", tags=["stats"])


# ── Schemas ────────────────────────────────────────────────────────────────


class DashboardStats(BaseModel):
    total_tunnels: int
    running: int
    errors: int
    traffic: str
    servers: int
    users: int
    speed_tests: int


class ActivityEntry(BaseModel):
    id: int
    level: str
    message: str
    created_at: str


# ── Helpers ────────────────────────────────────────────────────────────────


def _human_bytes(n: int) -> str:
    """Format a byte count as a human-readable string (e.g. ``'12.4 GB'``)."""
    if n is None or n < 0:
        return "0 GB"
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if value < 1024.0 or unit == "PB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return "0 GB"


# ── Routes ─────────────────────────────────────────────────────────────────


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DashboardStats:
    """Aggregate counters for the main dashboard card."""
    total_tunnels = db.query(func.count(Tunnel.id)).scalar() or 0
    running = db.query(func.count(Tunnel.id)).filter(Tunnel.status == "running").scalar() or 0
    errors = db.query(func.count(Tunnel.id)).filter(Tunnel.status == "error").scalar() or 0
    servers = db.query(func.count(Server.id)).scalar() or 0
    users = db.query(func.count(User.id)).scalar() or 0
    speed_tests = db.query(func.count(SpeedTestResult.id)).scalar() or 0
    traffic_bytes = (
        db.query(
            func.coalesce(func.sum(NodeMetric.network_rx_bytes), 0)
            + func.coalesce(func.sum(NodeMetric.network_tx_bytes), 0)
        ).scalar()
        or 0
    )
    return DashboardStats(
        total_tunnels=int(total_tunnels),
        running=int(running),
        errors=int(errors),
        traffic=_human_bytes(int(traffic_bytes)),
        servers=int(servers),
        users=int(users),
        speed_tests=int(speed_tests),
    )


@router.get("/activity", response_model=list[ActivityEntry])
async def activity(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=10, ge=1, le=200),
) -> list[ActivityEntry]:
    """Recent audit-log entries reshaped for the activity feed."""
    rows = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    entries: list[ActivityEntry] = []
    for r in rows:
        action = r.action or ""
        level = "error" if ("fail" in action.lower() or "error" in action.lower()) else "info"
        message = f"{action} {r.target}" if r.target else action
        created_at = r.timestamp.isoformat() if r.timestamp else ""
        entries.append(
            ActivityEntry(
                id=r.id,
                level=level,
                message=message,
                created_at=created_at,
            )
        )
    return entries
