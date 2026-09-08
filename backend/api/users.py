"""User management endpoints (admin-only)."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user, record_audit, require_admin
from core.security import hash_password
from db.models import User


router = APIRouter(prefix="/api/users", tags=["users"])


# ── Schemas ────────────────────────────────────────────────────────────────


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None
    quota_gb: float | None
    expiry_at: datetime | None


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$")
    password: str = Field(min_length=8, max_length=256)
    role: str = Field(default="user", pattern=r"^(admin|user)$")
    is_active: bool = True
    quota_gb: float | None = Field(default=None, ge=0)
    expiry_at: datetime | None = Field(default=None)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str | None = Field(default=None, min_length=8, max_length=256)
    role: str | None = Field(default=None, pattern=r"^(admin|user)$")
    is_active: bool | None = None
    quota_gb: float | None = Field(default=None, ge=0)
    expiry_at: datetime | None = Field(default=None)


# ── Routes ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[UserOut])
async def list_users(
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[UserOut]:
    users = db.query(User).order_by(User.id.asc()).all()
    return [UserOut.model_validate(u) for u in users]


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return UserOut.model_validate(user)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserOut:
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username already exists",
        )
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
        quota_gb=payload.quota_gb,
        expiry_at=payload.expiry_at,
    )
    db.add(user)
    db.flush()
    record_audit(
        db,
        action="user.create",
        user_id=admin.id,
        target=user.username,
        details={"role": user.role},
        request=request,
    )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.quota_gb is not None:
        user.quota_gb = payload.quota_gb
    if payload.expiry_at is not None:
        user.expiry_at = payload.expiry_at

    record_audit(
        db,
        action="user.update",
        user_id=admin.id,
        target=user.username,
        details=payload.model_dump(exclude_none=True),
        request=request,
    )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
async def delete_user(
    user_id: int,
    request: Request,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cannot delete the currently authenticated user",
        )
    target = user.username
    db.delete(user)
    record_audit(
        db,
        action="user.delete",
        user_id=admin.id,
        target=target,
        request=request,
    )
    db.commit()
    return None