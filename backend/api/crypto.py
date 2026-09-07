"""PSK and IPsec-algorithm management endpoints."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Annotated, Any

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.deps import get_current_user, record_audit
from core.security import generate_psk, mask_psk
from core.subprocess import CommandError, run_nosrat
from db.models import User


logger = logging.getLogger("nosrat.api.crypto")
router = APIRouter(prefix="/api/crypto", tags=["crypto"])


# ── Schemas ────────────────────────────────────────────────────────────────


class PskGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bits: int = Field(default=256, ge=128, le=1024)


class PskEntry(BaseModel):
    id: str
    name: str
    bits: int
    length: int
    preview: str
    masked: str
    path: str


class PskGenerateResponse(BaseModel):
    psk: str
    bits: int
    path: str


class PskRotateResponse(BaseModel):
    psk: str
    bits: int
    path: str


class AlgorithmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    algorithm: str = Field(
        default="aes256gcm16",
        pattern=r"^(aes256gcm16|aes128gcm16|aes256gcm12|aes128gcm12|aes256cbc|chacha20poly1305)$",
    )


class AlgorithmResponse(BaseModel):
    algorithm: str
    applied: bool
    detail: dict[str, Any] | None = None


# ── Storage helpers ────────────────────────────────────────────────────────


def _psk_dir() -> Path:
    p = Path(settings.psk_dir)
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    return p


async def _write_psk(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, mode="w", encoding="utf-8") as fh:
        await fh.write(value)
    try:
        path.chmod(0o600)
    except OSError:  # pragma: no cover
        pass


async def _read_psk(path: Path) -> str | None:
    try:
        async with aiofiles.open(path, mode="r", encoding="utf-8") as fh:
            return (await fh.read()).strip()
    except OSError:
        return None


def _list_psk_files() -> list[Path]:
    p = _psk_dir()
    return sorted([f for f in p.iterdir() if f.is_file()])


# ── Routes ─────────────────────────────────────────────────────────────────


@router.post("/psk/generate", response_model=PskGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate(
    payload: PskGenerateRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PskGenerateResponse:
    bits = 512 if payload.bits >= 512 else 256
    psk = generate_psk(bits)
    path = Path(settings.psk_file)
    await _write_psk(path, psk)

    record_audit(
        db,
        action="crypto.psk.generate",
        user_id=user.id,
        target=str(path),
        details={"bits": bits},
        request=request,
    )
    db.commit()
    return PskGenerateResponse(psk=psk, bits=bits, path=str(path))


@router.get("/psk/list", response_model=list[PskEntry])
async def list_psks(
    _user: Annotated[User, Depends(get_current_user)],
) -> list[PskEntry]:
    entries: list[PskEntry] = []
    for path in _list_psk_files():
        value = await _read_psk(path)
        if value is None:
            continue
        bits = len(value) * 4 if re.fullmatch(r"[0-9a-fA-F]+", value) else 0
        masked = mask_psk(value)
        entries.append(
            PskEntry(
                id=path.stem,
                name=path.name,
                bits=bits,
                length=masked["length"],
                preview=masked["preview"],
                masked=masked["masked"],
                path=str(path),
            )
        )
    return entries


@router.post("/psk/{psk_id}/rotate", response_model=PskRotateResponse)
async def rotate_psk(
    psk_id: str,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PskRotateResponse:
    """Rotate the active PSK. ``psk_id`` is informational; the active file is always overwritten."""
    psk = generate_psk(256)
    path = Path(settings.psk_file)

    # Try to stop the tunnel service first (best-effort).
    try:
        await run_nosrat("stop", check=False)
    except CommandError as exc:
        logger.warning("nosrat stop failed during PSK rotation: %s", exc)

    await _write_psk(path, psk)

    record_audit(
        db,
        action="crypto.psk.rotate",
        user_id=user.id,
        target=str(path),
        details={"psk_id": psk_id},
        request=request,
    )
    db.commit()
    return PskRotateResponse(psk=psk, bits=256, path=str(path))


@router.put("/algorithm", response_model=AlgorithmResponse)
async def set_algorithm(
    payload: AlgorithmRequest,
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AlgorithmResponse:
    cfg = Path(settings.config_file)
    if not cfg.exists():
        raise HTTPException(status_code=404, detail=f"config not found at {cfg}")
    try:
        async with aiofiles.open(cfg, mode="r", encoding="utf-8") as fh:
            body = await fh.read()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    new_body, count = re.subn(
        r"^(\s*encryption:\s*).*$",
        rf"\g<1>{payload.algorithm}",
        body,
        flags=re.MULTILINE,
    )
    if count == 0:
        new_body, count = re.subn(
            r"^(ipsec:\s*$)",
            rf"\1\n  encryption: {payload.algorithm}",
            body,
            flags=re.MULTILINE,
        )
    if count == 0:
        raise HTTPException(
            status_code=500,
            detail="could not locate ipsec.encryption in config",
        )

    await _write_psk(cfg, new_body)  # reuse chmod helper
    try:
        restart = await run_nosrat("restart", check=False, timeout=settings.long_command_timeout_sec)
        detail: dict[str, Any] = {"stdout": restart.stdout, "returncode": restart.returncode}
        applied = restart.returncode == 0
    except CommandError as exc:
        applied = False
        detail = {"error": str(exc), "stderr": exc.stderr}

    record_audit(
        db,
        action="crypto.algorithm.set",
        user_id=user.id,
        target=str(cfg),
        details={"algorithm": payload.algorithm, "applied": applied},
        request=request,
    )
    db.commit()
    return AlgorithmResponse(algorithm=payload.algorithm, applied=applied, detail=detail)