"""Health check + continuous monitoring endpoints."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.deps import get_current_user
from core.subprocess import CommandError, run
from db.models import User


logger = logging.getLogger("nosrat.api.health")
router = APIRouter(prefix="/api/health", tags=["health"])


# ── Schemas ────────────────────────────────────────────────────────────────


class CheckResult(BaseModel):
    name: str
    ok: bool
    detail: str | None = None
    latency_ms: float | None = None


class CheckResponse(BaseModel):
    overall_ok: bool
    checks: list[CheckResult]
    timestamp: datetime


class MonitorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_seconds: int = Field(default=60, ge=10, le=3600)
    interval_seconds: int = Field(default=5, ge=1, le=60)


class MonitorSample(BaseModel):
    timestamp: datetime
    gre_up: bool
    ipsec_up: bool
    service_up: bool
    packet_loss_pct: float | None
    latency_ms: float | None


class MonitorResponse(BaseModel):
    samples: list[MonitorSample]
    started_at: datetime
    finished_at: datetime
    remote_ip: str | None


# ── Helpers ────────────────────────────────────────────────────────────────


async def _ip_link(name: str) -> bool:
    try:
        result = await run(["ip", "link", "show", name], timeout=5, check=False)
        return result.returncode == 0
    except CommandError:
        return False


async def _service_active(unit: str) -> bool:
    try:
        result = await run(
            ["systemctl", "is-active", unit],
            timeout=5,
            check=False,
        )
        return result.stdout.strip() == "active"
    except CommandError:
        return False


async def _ipsec_active() -> bool:
    try:
        result = await run(["ip", "xfrm", "state"], timeout=5, check=False)
        return result.returncode == 0 and "esp" in result.stdout
    except CommandError:
        return False


async def _ping(host: str, *, count: int = 3, timeout: int = 5) -> tuple[bool, float | None, float | None]:
    try:
        result = await run(
            ["ping", "-c", str(count), "-W", str(timeout), host],
            timeout=timeout * count + 5,
        )
    except CommandError:
        return False, None, None
    text = result.stdout
    latency: float | None = None
    loss: float | None = None
    for line in text.splitlines():
        if "rtt min/avg/max" in line or "round-trip" in line:
            try:
                stats = line.split("=")[1].split("/")
                latency = float(stats[1])
            except (IndexError, ValueError):
                pass
        m = re.search(r"(\d+(?:\.\d+)?)%\s+packet loss", line)
        if m:
            try:
                loss = float(m.group(1))
            except ValueError:
                pass
    return result.returncode == 0, latency, loss


def _read_remote_ip() -> str | None:
    cfg = Path(settings.config_file)
    if not cfg.exists():
        return None
    try:
        for line in cfg.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("public_ip:"):
                value = line.split(":", 1)[1].strip().strip('"').strip("'")
                if value and value != "IRAN_SERVER_IP":
                    return value
    except OSError as exc:
        logger.warning("could not read remote ip from config: %s", exc)
    return None


# ── Routes ─────────────────────────────────────────────────────────────────


@router.get("/live", response_model=CheckResponse)
async def liveness() -> CheckResponse:
    """Cheap, unauthenticated liveness probe used by orchestrators."""
    db_ok = True
    try:
        from core.database import engine

        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception:  # noqa: BLE001
        db_ok = False
    checks = [CheckResult(name="database", ok=db_ok)]
    return CheckResponse(
        overall_ok=db_ok,
        checks=checks,
        timestamp=datetime.utcnow(),
    )


@router.post("/check", response_model=CheckResponse)
async def deep_check(
    _user: Annotated[User, Depends(get_current_user)],
) -> CheckResponse:
    """Authenticated detailed health check."""
    checks: list[CheckResult] = []

    gre_up, gre_lat = await asyncio.gather(
        _ip_link("nosrat"),
        _ping("127.0.0.1", count=1, timeout=2),
    )
    checks.append(CheckResult(name="gre_interface", ok=bool(gre_up)))
    checks.append(CheckResult(name="loopback_ping", ok=gre_lat[0], latency_ms=gre_lat[1]))

    ipsec_up = await _ipsec_active()
    checks.append(CheckResult(name="ipsec_sa", ok=ipsec_up))

    for unit in ("nosrat", "strongswan"):
        ok = await _service_active(unit)
        checks.append(CheckResult(name=f"service:{unit}", ok=ok))

    remote = _read_remote_ip()
    if remote:
        ok, latency, _loss = await _ping(remote, count=3, timeout=5)
        checks.append(CheckResult(name=f"remote:{remote}", ok=ok, latency_ms=latency))

    overall = all(c.ok for c in checks)
    return CheckResponse(overall_ok=overall, checks=checks, timestamp=datetime.utcnow())


@router.post("/monitor", response_model=MonitorResponse)
async def monitor(
    payload: MonitorRequest,
    _user: Annotated[User, Depends(get_current_user)],
) -> MonitorResponse:
    """Collect health samples over ``duration_seconds`` at ``interval_seconds`` cadence."""
    started = datetime.utcnow()
    samples: list[MonitorSample] = []
    remote_ip = _read_remote_ip()

    elapsed = 0
    while elapsed < payload.duration_seconds:
        ts = datetime.utcnow()
        gre_up = await _ip_link("nosrat")
        ipsec_up = await _ipsec_active()
        svc_up = await _service_active("nosrat")
        latency = loss = None
        if remote_ip:
            ok, latency, loss = await _ping(remote_ip, count=1, timeout=3)
            if not ok:
                latency = None
                loss = 100.0
        samples.append(
            MonitorSample(
                timestamp=ts,
                gre_up=gre_up,
                ipsec_up=ipsec_up,
                service_up=svc_up,
                packet_loss_pct=loss,
                latency_ms=latency,
            )
        )
        await asyncio.sleep(payload.interval_seconds)
        elapsed += payload.interval_seconds

    return MonitorResponse(
        samples=samples,
        started_at=started,
        finished_at=datetime.utcnow(),
        remote_ip=remote_ip,
    )