"""Authentication, password hashing and JWT helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import settings


# bcrypt has a 72-byte input limit; we hash the password with sha256 first
# when needed so users can use passphrases of any reasonable length.
_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_rounds,
)


class SecurityError(Exception):
    """Raised when authentication or token validation fails."""


# ── Password ───────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    if not password:
        raise ValueError("password must not be empty")
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time password verification."""
    if not plain or not hashed:
        return False
    try:
        return _pwd_context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


# ── JWT ─────────────────────────────────────────────────────────────────────


def create_access_token(
    subject: str | int,
    *,
    extra: dict[str, Any] | None = None,
    expires_minutes: int | None = None,
) -> str:
    """Mint a JWT for the given subject (typically a user id)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    subject: str | int,
    *,
    expires_minutes: int | None = None,
) -> str:
    """Mint a longer-lived refresh token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes or settings.refresh_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises SecurityError on failure."""
    if not token:
        raise SecurityError("empty token")
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise SecurityError(f"invalid token: {exc}") from exc


# ── PSK helpers ────────────────────────────────────────────────────────────


def generate_psk(bits: int = 256) -> str:
    """Generate a cryptographically strong Pre-Shared Key."""
    import secrets

    if bits not in (256, 512):
        raise ValueError("bits must be 256 or 512")
    nbytes = bits // 8
    return secrets.token_hex(nbytes)


def mask_psk(psk: str, *, prefix: int = 8, suffix: int = 8) -> dict[str, Any]:
    """Return a masked view of a PSK (used for safe display)."""
    if not psk:
        return {"length": 0, "preview": "", "masked": ""}
    length = len(psk)
    if length <= prefix + suffix:
        head = psk[:prefix]
        tail = ""
        masked = "*" * length
    else:
        head = psk[:prefix]
        tail = psk[-suffix:]
        masked = f"{head}{'*' * (length - prefix - suffix)}{tail}"
    return {
        "length": length,
        "preview": f"{head}...{tail}",
        "masked": masked,
    }