"""JWT-based authentication for ``nosrat-node`` agents.

These tokens are scoped to a single node (server row) and carry a
``type=node`` claim that distinguishes them from user access tokens.
The panel mints them at install time; the agent presents them when
opening the WebSocket and on every HTTP call to the local control API
forwarded through the panel.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from core.config import settings


logger = logging.getLogger("nosrat.agent_auth")


NODE_TOKEN_TYPE = "node"
AGENT_TOKEN_TYPE = "agent"  # alias used by the on-host local API

# Token scopes a node agent may hold.  Keep this list small & explicit –
# anything that can mutate the system should require an explicit scope.
NODE_SCOPES: dict[str, set[str]] = {
    "metrics": {"report:metrics", "read:self"},
    "command": {"exec:command", "read:self"},
    "logs": {"stream:logs", "read:self"},
    "register": {"write:self"},
    "update": {"write:self"},
}


class AgentAuthError(Exception):
    """Raised when an agent token is missing, expired or invalid."""


def _scopes_for(server_id: int) -> set[str]:
    """Return the full set of scopes a node token for ``server_id`` holds."""
    scopes: set[str] = set()
    for group in NODE_SCOPES.values():
        scopes |= group
    scopes.add(f"server:{server_id}")
    return scopes


def issue_node_token(
    server_id: int,
    *,
    node_name: str,
    location: str,
    expires_days: int = 365,
) -> str:
    """Mint a JWT that authenticates a node agent for ``server_id``.

    Tokens are long-lived (default 1 year) because re-issuing requires
    re-installing the agent.  The panel re-mints only on demand.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=expires_days)
    payload: dict[str, Any] = {
        "sub": f"node:{server_id}",
        "type": NODE_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(16),
        "server_id": int(server_id),
        "node_name": node_name,
        "location": location,
        "scopes": sorted(_scopes_for(server_id)),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    logger.info(
        "issued node token server_id=%s node=%s location=%s exp=%s",
        server_id,
        node_name,
        location,
        expire.isoformat(),
    )
    return token


def decode_node_token(token: str) -> dict[str, Any]:
    """Validate a node JWT and return its claims.

    Raises :class:`AgentAuthError` on any failure – never return ``None``
    so that callers don't have to disambiguate "missing" from "invalid".
    """
    if not token:
        raise AgentAuthError("empty token")
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise AgentAuthError(f"invalid token: {exc}") from exc
    if payload.get("type") not in (NODE_TOKEN_TYPE, AGENT_TOKEN_TYPE):
        raise AgentAuthError(f"wrong token type: {payload.get('type')!r}")
    if "server_id" not in payload:
        raise AgentAuthError("missing server_id claim")
    return payload


def has_scope(claims: dict[str, Any], scope: str) -> bool:
    """Return ``True`` if ``claims`` carries ``scope`` (or ``server:N``)."""
    scopes = claims.get("scopes") or []
    if scope in scopes:
        return True
    # ``server:N`` is an umbrella scope.
    server_scope = f"server:{claims.get('server_id')}"
    return server_scope in scopes


def authorize(token: str, *, required_scope: str | None = None) -> dict[str, Any]:
    """Decode ``token`` and optionally enforce ``required_scope``."""
    claims = decode_node_token(token)
    if required_scope and not has_scope(claims, required_scope):
        raise AgentAuthError(f"missing scope: {required_scope}")
    return claims


def extract_bearer(authorization_header: str | None) -> str | None:
    """Return the token from a ``Bearer <token>`` header (case-insensitive)."""
    if not authorization_header:
        return None
    parts = authorization_header.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def node_token_for(server: Any) -> str | None:
    """Return the persisted token for a ``Server`` row, if any."""
    return getattr(server, "node_token", None)