"""SQLAlchemy ORM models for the nosrat WebUI backend."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
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

    # ── Node agent state ───────────────────────────────────────────────
    node_installed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    node_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    node_token: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    node_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    node_location: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    node_status: Mapped[str] = mapped_column(String(32), default="offline", nullable=False)
    node_last_seen: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    node_install_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    node_install_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    node_install_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    node_install_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    metrics: Mapped[list["NodeMetric"]] = relationship(
        "NodeMetric", back_populates="server", cascade="all, delete-orphan"
    )
    commands: Mapped[list["NodeCommand"]] = relationship(
        "NodeCommand", back_populates="server", cascade="all, delete-orphan"
    )
    install_jobs: Mapped[list["NodeInstallJob"]] = relationship(
        "NodeInstallJob", back_populates="server", cascade="all, delete-orphan"
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


# ── Node agent metrics ─────────────────────────────────────────────────────


class NodeMetric(Base):
    """Per-server periodic metric sample reported by the node agent."""

    __tablename__ = "node_metrics"
    __table_args__ = (
        Index("ix_node_metrics_server_ts", "server_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(
        ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    cpu_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ram_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ram_used_mb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ram_total_mb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    disk_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    disk_used_gb: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    network_rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    network_tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    load_avg_1m: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    load_avg_5m: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    load_avg_15m: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    uptime_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hostname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    server: Mapped[Server] = relationship("Server", back_populates="metrics")


# ── Node command audit ─────────────────────────────────────────────────────


class NodeCommand(Base):
    """Audit trail for commands dispatched from the panel to a node agent."""

    __tablename__ = "node_commands"
    __table_args__ = (
        Index("ix_node_commands_server_ts", "server_id", "issued_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(
        ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    command_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    command: Mapped[str] = mapped_column(String(255), nullable=False)
    args: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    issued_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    server: Mapped[Server] = relationship("Server", back_populates="commands")


# ── Node install jobs ──────────────────────────────────────────────────────


class NodeInstallJob(Base):
    """Persistent record of an in-flight / completed node install."""

    __tablename__ = "node_install_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(
        ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    log: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    package_manager: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    os_info: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    server: Mapped[Server] = relationship("Server", back_populates="install_jobs")


# ── Node logs (in-panel cache of streamed logs) ────────────────────────────


class NodeLog(Base):
    """Bounded tail of log lines reported by the node agent."""

    __tablename__ = "node_logs"
    __table_args__ = (
        Index("ix_node_logs_server_ts", "server_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(
        ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="agent", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )