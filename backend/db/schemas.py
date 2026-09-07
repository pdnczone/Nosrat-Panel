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


# ── Node agent schemas ────────────────────────────────────────────────────


class NodeInfo(BaseModel):
    """Public view of a node agent."""

    model_config = ConfigDict(from_attributes=True)

    server_id: int
    node_name: str | None = None
    node_location: str | None = None
    node_version: str | None = None
    node_status: str = "offline"
    node_installed: bool = False
    node_last_seen: datetime | None = None
    node_install_started_at: datetime | None = None
    node_install_completed_at: datetime | None = None
    node_install_error: str | None = None


class NodeInstallRequest(BaseModel):
    """Request to start a node install on a server."""

    model_config = ConfigDict(extra="forbid")

    node_name: str | None = Field(default=None, min_length=1, max_length=128)
    location: str | None = Field(default=None, pattern=r"^(iran|external)$")
    force: bool = False


class NodeInstallResponse(BaseModel):
    job_id: int
    server_id: int
    status: str
    progress: int = Field(ge=0, le=100)
    started_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
    package_manager: str | None = None


class NodeInstallLogChunk(BaseModel):
    """Incremental log chunk returned by ``GET /install-status``."""

    job_id: int
    status: str
    progress: int
    tail: str
    error: str | None = None


class NodeInstallCommand(BaseModel):
    """Payload returned by the panel to the agent when registration completes."""

    model_config = ConfigDict(extra="forbid")

    action: str = Field(description="e.g. register, command, ping, update")
    node_name: str
    location: str
    panel_url: str
    token: str


class NodeMetricIn(BaseModel):
    """Metrics sample posted by the node agent."""

    model_config = ConfigDict(extra="ignore")

    timestamp: datetime | None = None
    cpu_percent: float = Field(ge=0, le=100)
    ram_percent: float = Field(ge=0, le=100)
    ram_used_mb: int = Field(ge=0)
    ram_total_mb: int = Field(ge=0)
    disk_percent: float = Field(ge=0, le=100)
    disk_used_gb: float = Field(ge=0)
    network_rx_bytes: int = Field(ge=0)
    network_tx_bytes: int = Field(ge=0)
    load_avg_1m: float = Field(ge=0)
    load_avg_5m: float = Field(ge=0)
    load_avg_15m: float = Field(ge=0)
    uptime_seconds: int = Field(ge=0)
    hostname: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class NodeMetricOut(ORMBase):
    id: int
    server_id: int
    timestamp: datetime
    cpu_percent: float
    ram_percent: float
    ram_used_mb: int
    ram_total_mb: int
    disk_percent: float
    disk_used_gb: float
    network_rx_bytes: int
    network_tx_bytes: int
    load_avg_1m: float
    load_avg_5m: float
    load_avg_15m: float
    uptime_seconds: int
    hostname: str | None


class NodeCommandRequest(BaseModel):
    """Body of ``POST /api/nodes/{id}/command``."""

    model_config = ConfigDict(extra="forbid")

    command: str = Field(min_length=1, max_length=255)
    args: dict[str, Any] = Field(default_factory=dict)
    timeout: int = Field(default=60, ge=1, le=3600)


class NodeCommandOut(ORMBase):
    id: int
    server_id: int
    command_id: str
    command: str
    args: dict[str, Any]
    issued_at: datetime
    completed_at: datetime | None
    status: str
    stdout: str | None
    stderr: str | None
    exit_code: int | None


class NodeCommandResultIn(BaseModel):
    """Body of a ``command_result`` message sent by the agent."""

    model_config = ConfigDict(extra="ignore")

    command_id: str
    status: str = Field(pattern=r"^(success|failed|running)$")
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None


class NodeLogIn(BaseModel):
    """Single log line reported by the agent."""

    model_config = ConfigDict(extra="ignore")

    level: str = Field(default="info", pattern=r"^(debug|info|warn|error)$")
    source: str = Field(default="agent", max_length=64)
    message: str = Field(min_length=1, max_length=8192)
    timestamp: datetime | None = None


class NodeLogOut(ORMBase):
    id: int
    server_id: int
    level: str
    source: str
    message: str
    timestamp: datetime


class NodeRegisterIn(BaseModel):
    """Body of the ``register`` message from the agent."""

    model_config = ConfigDict(extra="ignore")

    node_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=32)
    hostname: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, pattern=r"^(iran|external)$")
    os: dict[str, Any] = Field(default_factory=dict)
    interfaces: list[dict[str, Any]] = Field(default_factory=list)


# ── WebSocket envelope shared by node ↔ panel ─────────────────────────────


class WSEnvelope(BaseModel):
    """Envelope used by both directions of the node WebSocket."""

    model_config = ConfigDict(extra="ignore")

    type: str = Field(min_length=1, max_length=32)
    id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


# ── Server with embedded node fields (for UI convenience) ─────────────────


class ServerNodeOut(BaseModel):
    """Composite of ``ServerOut`` + node fields, used by the WebUI."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    host: str
    ssh_port: int
    ssh_user: str
    ssh_key_path: str | None
    status: str
    last_seen: datetime | None
    nosrat_version: str | None
    metadata_json: dict[str, Any] = Field(default_factory=dict, validation_alias="server_metadata")
    created_at: datetime
    # ── Node fields ─────────────────────────────────────────────────────
    node_installed: bool = False
    node_version: str | None = None
    node_name: str | None = None
    node_location: str | None = None
    node_status: str = "offline"
    node_last_seen: datetime | None = None
    node_install_started_at: datetime | None = None
    node_install_completed_at: datetime | None = None
    node_install_error: str | None = None