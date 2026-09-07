"""Application settings KV endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
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


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
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