"""FastAPI dependencies (auth, role checks, audit-log helpers)."""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import SecurityError, decode_token
from db.models import AuditLog, User


logger = logging.getLogger("nosrat.auth")


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False,
)


def _unauthorized(message: str = "invalid credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(message: str = "forbidden") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated user or raise 401."""
    if not token:
        raise _unauthorized("missing bearer token")
    try:
        payload = decode_token(token)
    except SecurityError as exc:
        raise _unauthorized(str(exc)) from exc

    if payload.get("type") != "access":
        raise _unauthorized("wrong token type")

    sub = payload.get("sub")
    if sub is None:
        raise _unauthorized("missing subject")

    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise _unauthorized("invalid subject") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("user not found or inactive")

    # Enforce expiry limits for non-admin users
    now = datetime.now(timezone.utc)
    if user.role != "admin":
        if user.expiry_at and user.expiry_at <= now:
            raise _forbidden("account expired")
        # Note: panel-user quota_gb is informational. Real per-tunnel
        # per-client quota enforcement lives in TunnelClient + services/usage.py

    return user


def require_role(*roles: str) -> Callable[[User], User]:
    """Dependency factory that enforces a role check."""

    allowed = {r.lower() for r in roles}

    def _checker(user: User = Depends(get_current_user)) -> User:
        if allowed and user.role.lower() not in allowed:
            raise _forbidden(
                f"requires role in {sorted(allowed)}, got '{user.role}'"
            )
        return user

    return _checker


require_admin = require_role("admin")
require_user = require_role("admin", "user")


def record_audit(
    db: Session,
    *,
    action: str,
    user_id: int | None = None,
    target: str | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Persist an audit entry. Caller is expected to commit."""
    ip: str | None = None
    if request is not None:
        ip = request.client.host if request.client else None
        if not ip:
            ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or None

    entry = AuditLog(
        user_id=user_id,
        action=action,
        target=target,
        details=details or {},
        ip_address=ip,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()
    return entry