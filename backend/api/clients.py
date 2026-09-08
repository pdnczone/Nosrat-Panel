"""TunnelClient (VPN subscriber) management API — quota, expiry, usage.

Separate from ``users.py`` (panel operator accounts). These endpoints let an
admin define VPN clients, set data quotas and expiry windows, renew/top up, and
view real consumption samples relative to quota.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import record_audit, require_admin
from db.models import Tunnel, TunnelClient, UsageSample, User

router = APIRouter(prefix="/api/clients", tags=["clients"])

STATUSES = ("active", "over_quota", "expired", "disabled")


# ── Schemas ────────────────────────────────────────────────────────────────


class UsageSampleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sampled_at: datetime
    rx_bytes: int
    tx_bytes: int
    total_bytes: int
    over_quota: bool


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    tunnel_id: int | None
    server_id: int | None
    peer_identifier: str | None
    quota_bytes: int
    used_bytes: int
    expires_at: datetime | None
    status: str
    note: str | None
    created_at: datetime
    updated_at: datetime


class ClientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128)
    tunnel_id: int | None = None
    server_id: int | None = None
    peer_identifier: str | None = Field(default=None, max_length=255)
    quota_bytes: int = Field(default=0, ge=0)
    expires_at: datetime | None = None
    note: str | None = Field(default=None, max_length=512)


class ClientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=128)
    peer_identifier: str | None = Field(default=None, max_length=255)
    quota_bytes: int | None = Field(default=None, ge=0)
    used_bytes: int | None = Field(default=None, ge=0)
    expires_at: datetime | None = Field(default=None)
    note: str | None = Field(default=None, max_length=512)
    status: str | None = Field(default=None, pattern="|".join(STATUSES))


class ClientUsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    quota_bytes: int
    used_bytes: int
    remaining_bytes: int
    pct_used: float
    status: str
    expires_at: datetime | None
    samples: list[UsageSampleOut]


# ── Helpers ────────────────────────────────────────────────────────────────


def _get_client_or_404(db: Session, client_id: int) -> TunnelClient:
    client = db.get(TunnelClient, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    return client


def _validate_attach(db: Session, tunnel_id: int | None, server_id: int | None) -> None:
    if tunnel_id is not None and db.get(Tunnel, tunnel_id) is None:
        raise HTTPException(status_code=404, detail="tunnel not found")
    if server_id is not None:
        from db.models import Server

        if db.get(Server, server_id) is None:
            raise HTTPException(status_code=404, detail="server not found")


# ── Routes ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[ClientOut])
async def list_clients(
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: str | None = Query(default=None, description="filter by status"),
) -> list[ClientOut]:
    q = db.query(TunnelClient)
    if status_filter:
        q = q.filter(TunnelClient.status == status_filter)
    return [ClientOut.model_validate(c) for c in q.order_by(TunnelClient.id.asc()).all()]


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> ClientOut:
    _validate_attach(db, payload.tunnel_id, payload.server_id)
    if payload.tunnel_id is None and payload.server_id is None:
        raise HTTPException(status_code=400, detail="tunnel_id or server_id required")
    client = TunnelClient(**payload.model_dump())
    db.add(client)
    db.flush()
    record_audit(
        db,
        action="client.create",
        user_id=admin.id,
        target=client.name,
        details={"quota_bytes": client.quota_bytes, "expires_at": client.expires_at and client.expires_at.isoformat()},
        request=request,
    )
    db.commit()
    db.refresh(client)
    return ClientOut.model_validate(client)


@router.get("/{client_id}", response_model=ClientOut)
async def get_client(
    client_id: int,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ClientOut:
    return ClientOut.model_validate(_get_client_or_404(db, client_id))


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client(
    client_id: int,
    payload: ClientUpdate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> ClientOut:
    client = _get_client_or_404(db, client_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(client, field, value)
    record_audit(
        db,
        action="client.update",
        user_id=admin.id,
        target=client.name,
        details=payload.model_dump(exclude_none=True),
        request=request,
    )
    db.commit()
    db.refresh(client)
    return ClientOut.model_validate(client)


@router.post("/{client_id}/topup", response_model=ClientOut)
async def topup_client(
    client_id: int,
    payload: ClientUpdate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> ClientOut:
    client = _get_client_or_404(db, client_id)
    if payload.quota_bytes:
        client.quota_bytes = payload.quota_bytes
    if payload.expires_at:
        client.expires_at = payload.expires_at
    # Re-activate after top-up / renewal.
    client.status = "active"
    record_audit(
        db,
        action="client.topup",
        user_id=admin.id,
        target=client.name,
        details={"quota_bytes": client.quota_bytes, "expires_at": client.expires_at and client.expires_at.isoformat()},
        request=request,
    )
    db.commit()
    db.refresh(client)
    return ClientOut.model_validate(client)


@router.get("/{client_id}/usage", response_model=ClientUsageOut)
async def client_usage(
    client_id: int,
    _admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=50, ge=1, le=500),
) -> ClientUsageOut:
    client = _get_client_or_404(db, client_id)
    samples = (
        db.query(UsageSample)
        .filter(UsageSample.client_id == client_id)
        .order_by(UsageSample.sampled_at.desc())
        .limit(limit)
        .all()
    )
    samples = list(reversed(samples))
    remaining = max(0, client.quota_bytes - client.used_bytes) if client.quota_bytes > 0 else client.used_bytes
    pct = (client.used_bytes / client.quota_bytes * 100.0) if client.quota_bytes > 0 else 0.0
    return ClientUsageOut(
        quota_bytes=client.quota_bytes,
        used_bytes=client.used_bytes,
        remaining_bytes=remaining,
        pct_used=round(pct, 2),
        status=client.status,
        expires_at=client.expires_at,
        samples=[UsageSampleOut.model_validate(s) for s in samples],
    )


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
async def delete_client(
    client_id: int,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> None:
    client = _get_client_or_404(db, client_id)
    target = client.name
    record_audit(db, action="client.delete", user_id=admin.id, target=target, request=request)
    db.delete(client)
    db.commit()
    return None
