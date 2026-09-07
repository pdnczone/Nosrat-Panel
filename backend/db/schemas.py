"""Pydantic v2 schemas shared across routers."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class ORMBase(BaseModel):
    """Base for response models that mirror an ORM row."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class Page(BaseModel, Generic[T]):
    """Generic paginated response envelope."""

    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1, default=1)
    page_size: int = Field(ge=1, le=500, default=50)


class StatusResponse(BaseModel):
    """Common status envelope returned by mutation endpoints."""

    ok: bool = True
    message: str | None = None
    data: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Common error envelope returned on failure."""

    ok: bool = False
    error: str
    code: str | None = None
    details: dict[str, Any] | None = None


class HealthInfo(BaseModel):
    status: str = "ok"
    version: str
    uptime_seconds: float
    database: str
    environment: str


class AuditOut(ORMBase):
    id: int
    user_id: int | None
    action: str
    target: str | None
    details: dict[str, Any]
    ip_address: str | None
    timestamp: datetime