"""Application settings KV endpoints."""
from __future__ import annotations

import io
import json
import tarfile
import time
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, RootModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user, record_audit, require_admin
from core.subprocess import CommandError, run_nosrat
from db.models import Setting, User


router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── Schemas ────────────────────────────────────────────────────────────────


class SettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    value: Any
    updated_at: datetime


class SettingsPayload(RootModel[dict[str, Any]]):
    """Whole-bulk update — body is a flat ``{key: value}`` object."""


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: dict[str, Any] = Field(default_factory=dict)


# ── Routes ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[SettingOut])
async def get_settings(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SettingOut]:
    rows = db.query(Setting).order_by(Setting.key.asc()).all()
    return [SettingOut.model_validate(r) for r in rows]


@router.put("", response_model=list[SettingOut])
async def bulk_update(
    payload: SettingsUpdate,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SettingOut]:
    for key, value in payload.items.items():
        if not isinstance(key, str) or not key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="setting keys must be non-empty strings",
            )
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value))
        else:
            row.value = value
    record_audit(
        db,
        action="settings.bulk_update",
        user_id=admin.id,
        details={"keys": sorted(payload.items.keys())},
        request=request,
    )
    db.commit()
    rows = db.query(Setting).order_by(Setting.key.asc()).all()
    return [SettingOut.model_validate(r) for r in rows]


@router.put("/{key}", response_model=SettingOut)
async def set_setting(
    key: str,
    payload: SettingsPayload,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SettingOut:
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="key required",
        )
    row = db.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=payload.root)
        db.add(row)
    else:
        row.value = payload.root
    record_audit(
        db,
        action="settings.set",
        user_id=admin.id,
        target=key,
        details={"value": payload.root},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return SettingOut.model_validate(row)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
async def delete_setting(
    key: str,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    row = db.get(Setting, key)
    if row is None:
        raise HTTPException(status_code=404, detail="setting not found")
    db.delete(row)
    record_audit(
        db,
        action="settings.delete",
        user_id=admin.id,
        target=key,
        request=request,
    )
    db.commit()
    return None


@router.get("/backup")
async def backup_settings(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Download all settings as a tar.gz containing ``settings.json``."""
    rows = db.query(Setting).all()
    payload = {r.key: r.value for r in rows}
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        data = json.dumps(payload, indent=2, default=str).encode("utf-8")
        info = tarfile.TarInfo(name="settings.json")
        info.size = len(data)
        info.mtime = int(time.time())
        tar.addfile(info, io.BytesIO(data))
    return Response(
        content=buf.getvalue(),
        media_type="application/gzip",
        headers={"Content-Disposition": 'attachment; filename="nosrat-settings-backup.tar.gz"'},
    )


@router.post("/restore")
async def restore_settings(
    file: Annotated[UploadFile, File(...)],
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, int]:
    """Restore settings from a backup tar.gz containing ``settings.json``."""
    data = await file.read()
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            member = tar.getmember("settings.json")
            fh = tar.extractfile(member)
            if fh is None:
                raise HTTPException(status_code=400, detail="settings.json missing from archive")
            payload = json.loads(fh.read().decode("utf-8"))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"invalid backup archive: {exc}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="settings.json must be a JSON object")
    restored = 0
    for key, value in payload.items():
        if not isinstance(key, str) or not key:
            continue
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value))
        else:
            row.value = value
        restored += 1
    record_audit(
        db,
        action="settings.restore",
        user_id=admin.id,
        details={"restored": restored},
        request=request,
    )
    db.commit()
    return {"restored": restored}


# ── Routes ─────────────────────────────────────────────────────────────────