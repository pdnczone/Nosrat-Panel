"""Fernet-based encryption for sensitive metadata fields."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet
from core.config import settings

_PREFIX = "ENC:"
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = hashlib.sha256(settings.secret_key.encode()).digest()
        _fernet = Fernet(__import__("base64").urlsafe_b64encode(key))
    return _fernet


def encrypt_value(value: str) -> str:
    """Encrypt a string value. Idempotent — already-encrypted values are returned as-is."""
    if value.startswith(_PREFIX):
        return value
    f = _get_fernet()
    return _PREFIX + f.encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    """Decrypt an encrypted string. Non-encrypted values are returned as-is."""
    if not value.startswith(_PREFIX):
        return value
    f = _get_fernet()
    return f.decrypt(value[len(_PREFIX):].encode()).decode()


SENSITIVE_KEYS = {"ssh_private_key", "ssh_password"}


def encrypt_metadata(meta: dict[str, Any] | None) -> dict[str, Any]:
    """Encrypt sensitive fields in metadata dict."""
    if not meta:
        return meta
    result = dict(meta)
    for key in SENSITIVE_KEYS:
        if key in result and isinstance(result[key], str) and not result[key].startswith(_PREFIX):
            result[key] = encrypt_value(result[key])
    return result


def decrypt_metadata(meta: dict[str, Any] | None) -> dict[str, Any]:
    """Decrypt sensitive fields in metadata dict."""
    if not meta:
        return meta
    result = dict(meta)
    for key in SENSITIVE_KEYS:
        if key in result and isinstance(result[key], str):
            result[key] = decrypt_value(result[key])
    return result
