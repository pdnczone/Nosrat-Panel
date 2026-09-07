"""Authentication endpoints: login, logout, refresh, current-user."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.deps import get_current_user, record_audit
from core.security import (
    SecurityError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from db.models import User


logger = logging.getLogger("nosrat.api.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Schemas ────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int = Field(
        default=settings.access_token_expire_minutes * 60, ge=1
    )


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=10)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None


# ── Routes ─────────────────────────────────────────────────────────────────


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = (
        db.query(User).filter(User.username == payload.username).first()
    )
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        record_audit(
            db,
            action="auth.login.failed",
            target=payload.username,
            details={"reason": "bad_credentials"},
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )

    user.last_login = datetime.now(timezone.utc)
    db.flush()

    access = create_access_token(
        user.id, extra={"role": user.role, "username": user.username}
    )
    refresh = create_refresh_token(user.id)

    record_audit(
        db,
        action="auth.login.success",
        user_id=user.id,
        target=user.username,
        details={"ip": request.client.host if request.client else None},
        request=request,
    )
    db.commit()
    db.refresh(user)

    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Stateless logout — the client simply discards the token.

    We still log the event so the audit trail reflects the explicit logout.
    """
    record_audit(
        db,
        action="auth.logout",
        user_id=user.id,
        target=user.username,
        request=request,
    )
    db.commit()
    return {"ok": True, "message": "logged out"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        decoded = decode_token(payload.refresh_token)
    except SecurityError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    if decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not a refresh token",
        )

    sub = decoded.get("sub")
    try:
        user_id = int(sub) if sub is not None else None
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid subject",
        ) from exc

    user = db.get(User, user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user not found or inactive",
        )

    access = create_access_token(
        user.id, extra={"role": user.role, "username": user.username}
    )
    new_refresh = create_refresh_token(user.id)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)