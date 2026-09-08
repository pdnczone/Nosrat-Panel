"""Centralized SSH credential resolution using metadata_crypto.decrypt_metadata.

This is the SINGLE code path for turning stored server metadata into usable
SSH credentials. All callers (servers API, node installer, SSH terminal, etc.)
must go through this function. Never read server.server_metadata.get("ssh_password")
or .get("ssh_private_key") directly.
"""
from __future__ import annotations

from typing import Any

from core.metadata_crypto import decrypt_value
from db.models import Server


def resolve_ssh_credentials(server: Server) -> dict[str, str | None]:
    """Decrypt and return SSH credentials for a server.

    Returns a dict with keys:
    - "password": decrypted password or None
    - "private_key": decrypted private key or None

    At least one of password/private_key must be present for SSH auth to work.
    """
    meta = server.server_metadata or {}
    enc_password = meta.get("ssh_password")
    enc_private_key = meta.get("ssh_private_key")

    password = decrypt_value(enc_password) if enc_password else None
    private_key = decrypt_value(enc_private_key) if enc_private_key else None

    return {"password": password, "private_key": private_key}