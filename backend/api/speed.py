"""Speed-test / latency endpoints."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.deps import get_current_user
from core.subprocess import CommandError, run, run_shell
from db.models import SpeedTestResult, User


logger = logging.getLogger("nosrat.api.speed")
router = APIRouter(prefix="/api/speed", tags=["speed"])


# ── Schemas ────────────────────────────────────────────────────────────────


class PingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str | None = Field(default=None, max_length=255)
    count: int = Field(default=10, ge=1, le=100)
    interval_ms: int = Field(default=500, ge=100, le=5000)


class PingResult(BaseModel):
    target: str
    transmitted: int
    received: int
    loss_pct: float
    latency_ms_avg: float | None
    latency_ms_min: float | None
    latency_ms_max: float | None
    raw: str | None = None


class SpeedTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str | None = Field(default=None, max_length=255)
    duration_sec: int = Field(default=10, ge=1, le=120)
    parallel: int = Field(default=4, ge=1, le=16)


class SpeedTestResultSchema(BaseModel):
    mode: str  # "ping" | "iperf3" | "nc"
    target: str
    ok: bool
    latency_ms: float | None
    loss_pct: float | None
    throughput_mbps: float | None
    detail: dict[str, Any] | None = None


class SpeedHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tunnel_id: int | None
    target: str
    latency_ms: float | None
    loss_pct: float | None
    throughput_mbps: float | None
    raw: dict[str, Any]
    timestamp: datetime


# ── Helpers ────────────────────────────────────────────────────────────────


def _parse_ping(output: str) -> dict[str, float | int | None]:
    stats = {"transmitted": 0, "received": 0, "loss_pct": 0.0, "latency_ms_avg": None, "latency_ms_min": None, "latency_ms_max": None}
    for line in output.splitlines():
        m = re.search(r"(\d+)\s+packets transmitted,\s+(\d+)\s+received,\s+([\d\.]+)%", line)
        if m:
            stats["transmitted"] = int(m.group(1))
            stats["received"] = int(m.group(2))
            stats["loss_pct"] = float(m.group(3))
        if "rtt min/avg/max" in line or "round-trip" in line:
            try:
                nums = line.split("=")[1].split("/")
                stats["latency_ms_min"] = float(nums[0])
                stats["latency_ms_avg"] = float(nums[1])
                stats["latency_ms_max"] = float(nums[2].split(" ")[0])
            except (IndexError, ValueError):
                pass
    return stats


def _default_target() -> str | None:
    cfg = Path(settings.config_file)
    if not cfg.exists():
        return None
    try:
        text = cfg.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("public_ip:"):
            value = line.split(":", 1)[1].strip().strip('"').strip("'")
            if value and value != "IRAN_SERVER_IP":
                return value
    return None


# ── Routes ─────────────────────────────────────────────────────────────────


@router.post("/ping", response_model=PingResult)
async def ping(
    payload: PingRequest,
    _user: Annotated[User, Depends(get_current_user)],
) -> PingResult:
    target = payload.target or _default_target()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no target supplied and no remote IP in config",
        )

    try:
        result = await run(
            ["ping", "-c", str(payload.count), "-i", str(payload.interval_ms / 1000.0), target],
            timeout=min(60, max(5, payload.count * 2)),
        )
    except CommandError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    parsed = _parse_ping(result.stdout)
    return PingResult(
        target=target,
        transmitted=parsed["transmitted"],  # type: ignore[arg-type]
        received=parsed["received"],  # type: ignore[arg-type]
        loss_pct=parsed["loss_pct"],  # type: ignore[arg-type]
        latency_ms_avg=parsed["latency_ms_avg"],  # type: ignore[arg-type]
        latency_ms_min=parsed["latency_ms_min"],  # type: ignore[arg-type]
        latency_ms_max=parsed["latency_ms_max"],  # type: ignore[arg-type]
        raw=result.stdout if result.returncode != 0 else None,
    )


@router.post("/test", response_model=SpeedTestResultSchema)
async def speed_test(
    payload: SpeedTestRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SpeedTestResultSchema:
    """Try iperf3 if available, otherwise a netcat/throughput probe."""
    target = payload.target or _default_target()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no target supplied and no remote IP in config",
        )

    latency_ms: float | None = None
    loss_pct: float | None = None
    throughput_mbps: float | None = None
    mode = "ping"
    detail: dict[str, Any] = {}

    # Latency probe first.
    try:
        ping_result = await run(["ping", "-c", "5", "-W", "3", target], timeout=20)
        parsed = _parse_ping(ping_result.stdout)
        latency_ms = parsed["latency_ms_avg"]  # type: ignore[assignment]
        loss_pct = parsed["loss_pct"]  # type: ignore[assignment]
        detail["ping_raw"] = ping_result.stdout
    except CommandError as exc:
        detail["ping_error"] = exc.stderr or str(exc)

    # iperf3 if installed.
    try:
        probe = await run(["which", "iperf3"], timeout=5, check=False)
    except CommandError as exc:
        probe = None  # type: ignore[assignment]
        detail["which_error"] = str(exc)

    if probe and probe.returncode == 0 and probe.stdout.strip():
        mode = "iperf3"
        try:
            iperf = await run(
                [
                    "iperf3",
                    "-c",
                    target,
                    "-t",
                    str(payload.duration_sec),
                    "-P",
                    str(payload.parallel),
                    "-J",
                ],
                timeout=max(payload.duration_sec * 2, 30),
            )
            import json as _json

            data = _json.loads(iperf.stdout)
            bits_per_second = data.get("end", {}).get("sum_received", {}).get("bits_per_second")
            if bits_per_second:
                throughput_mbps = bits_per_second / 1_000_000.0
            detail["iperf3"] = data
        except (CommandError, ValueError) as exc:
            detail["iperf3_error"] = str(exc)
            mode = "ping"
    else:
        mode = "ping"

    entry = SpeedTestResult(
        target=target,
        latency_ms=latency_ms,
        loss_pct=loss_pct,
        throughput_mbps=throughput_mbps,
        raw=detail,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return SpeedTestResultSchema(
        mode=mode,
        target=target,
        ok=loss_pct is None or loss_pct < 100.0,
        latency_ms=latency_ms,
        loss_pct=loss_pct,
        throughput_mbps=throughput_mbps,
        detail={"history_id": entry.id, **(detail or {})},
    )


@router.get("/history", response_model=list[SpeedHistoryItem])
async def history(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
) -> list[SpeedHistoryItem]:
    limit = max(1, min(limit, 500))
    rows = (
        db.query(SpeedTestResult)
        .order_by(SpeedTestResult.id.desc())
        .limit(limit)
        .all()
    )
    return [SpeedHistoryItem.model_validate(r) for r in rows]