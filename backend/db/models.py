"""SQLAlchemy ORM models for the nosrat WebUI backend."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.current_timestamp(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.current_timestamp(),
        nullable=False,
    )


# ── Users ───────────────────────────────────────────────────────────────────


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ── Servers ─────────────────────────────────────────────────────────────────


class Server(Base, TimestampMixin):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    ssh_port: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    ssh_user: Mapped[str] = mapped_column(String(64), default="root", nullable=False)
    ssh_key_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    last_seen: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    nosrat_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    server_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json", JSON, default=dict, nullable=False
    )

    tunnels: Mapped[list["Tunnel"]] = relationship(
        "Tunnel", back_populates="server", cascade="all, delete-orphan"
    )


# ── Tunnels ─────────────────────────────────────────────────────────────────


class Tunnel(Base, TimestampMixin):
    __tablename__ = "tunnels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("servers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    plugin: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    params: Mapped[dict[str, Any]] = mapped_column(
        "params_json", JSON, default=dict, nullable=False
    )
    config_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    last_status_check: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    server: Mapped[Optional[Server]] = relationship("Server", back_populates="tunnels")
    logs: Mapped[list["TunnelLog"]] = relationship(
        "TunnelLog", back_populates="tunnel", cascade="all, delete-orphan"
    )


# ── Tunnel Logs ─────────────────────────────────────────────────────────────


class TunnelLog(Base):
    __tablename__ = "tunnel_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tunnel_id: Mapped[int] = mapped_column(
        ForeignKey("tunnels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    tunnel: Mapped[Tunnel] = relationship("Tunnel", back_populates="logs")


# ── Settings KV ─────────────────────────────────────────────────────────────


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


# ── Audit Log ───────────────────────────────────────────────────────────────


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(
        "details_json", JSON, default=dict, nullable=False
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
        index=True,
    )


# ── Speed test history (used by /api/speed/history) ────────────────────────


class SpeedTestResult(Base):
    __tablename__ = "speed_test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tunnel_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tunnels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    loss_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    throughput_mbps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )