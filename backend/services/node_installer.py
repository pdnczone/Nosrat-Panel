"""Background service that installs the ``nosrat-node`` agent on a remote server.

The installer opens an SSH connection to the target host, detects the OS
and package manager, uploads the bundled ``install.sh`` (and supporting
files) and runs it with the credentials supplied by the panel.  Progress
is streamed into a :class:`NodeInstallJob` row and consumed by the UI
over ``GET /api/servers/{id}/install-status``.

The service is idempotent: re-running it on a server that already has a
node returns the existing job without contacting the remote host.  A
``force=True`` request will tear the old install down first.
"""
from __future__ import annotations

import asyncio
import logging
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.agent_auth import issue_node_token
from core.config import settings
from core.database import SessionLocal, session_scope
from core.ssh import SSHClient, SSHError
from db.models import NodeInstallJob, Server

# Where the bundled install script + systemd unit + agent.py live inside
# the panel repo.  The installer uploads these as a single tarball to the
# remote host and extracts them under ``/opt/nosrat-node``.
NODE_AGENT_DIR = Path(__file__).resolve().parent.parent.parent / "node-agent"


logger = logging.getLogger("nosrat.installer")


# ── Public helpers ────────────────────────────────────────────────────────


def start_install(
    server_id: int,
    *,
    node_name: str | None = None,
    location: str | None = None,
    force: bool = False,
    panel_url: str | None = None,
    initiated_by: int | None = None,
) -> NodeInstallJob:
    """Schedule a node install.  Returns the persisted ``NodeInstallJob``.

    The actual work is dispatched onto the event loop.  If a previous
    job for the same server is still running we re-attach to it unless
    ``force`` is set.
    """
    with session_scope() as db:
        server = db.get(Server, server_id)
        if server is None:
            raise LookupError(f"server {server_id} not found")

        existing = (
            db.query(NodeInstallJob)
            .filter(
                NodeInstallJob.server_id == server_id,
                NodeInstallJob.status.in_(("pending", "running")),
            )
            .order_by(NodeInstallJob.id.desc())
            .first()
        )
        if existing is not None and not force:
            logger.info(
                "install already in progress server=%s job=%s", server_id, existing.id
            )
            return existing

        if server.node_installed and not force:
            logger.info("node already installed on server=%s", server_id)

        job = NodeInstallJob(
            server_id=server_id,
            status="pending",
            progress=0,
            log="",
            package_manager=None,
            os_info={},
            started_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.flush()
        job_id = job.id
        server_id_copy = server_id

    # Dispatch the background task.  ``asyncio.create_task`` requires an
    # active event loop, which we always have under FastAPI / uvicorn.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        loop.create_task(
            _run_install(
                job_id=job_id,
                server_id=server_id_copy,
                node_name=node_name,
                location=location,
                panel_url=panel_url,
                force=force,
                initiated_by=initiated_by,
            )
        )
    else:
        # Fallback for unit tests / sync contexts.
        asyncio.run(
            _run_install(
                job_id=job_id,
                server_id=server_id_copy,
                node_name=node_name,
                location=location,
                panel_url=panel_url,
                force=force,
                initiated_by=initiated_by,
            )
        )

    with session_scope() as db:
        return db.get(NodeInstallJob, job_id)  # type: ignore[return-value]


def get_job(server_id: int) -> NodeInstallJob | None:
    """Return the latest job for ``server_id`` (any status)."""
    with session_scope() as db:
        return (
            db.query(NodeInstallJob)
            .filter(NodeInstallJob.server_id == server_id)
            .order_by(NodeInstallJob.id.desc())
            .first()
        )


def append_log(job_id: int, line: str) -> None:
    """Append a single line to the job's log buffer.

    Kept short (last 64 KiB) to avoid unbounded growth.  Runs in its own
    short-lived transaction.
    """
    with SessionLocal() as db:
        try:
            job = db.get(NodeInstallJob, job_id)
            if job is None:
                return
            buf = (job.log or "") + line + "\n"
            if len(buf) > 64 * 1024:
                buf = buf[-64 * 1024 :]
            job.log = buf
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("append_log failed job=%s: %s", job_id, exc)


# ── Implementation ────────────────────────────────────────────────────────


async def _run_install(
    *,
    job_id: int,
    server_id: int,
    node_name: str | None,
    location: str | None,
    panel_url: str | None,
    force: bool,
    initiated_by: int | None,
) -> None:
    """The actual install pipeline.  Never raises – failures land in the DB."""
    panel_url = (panel_url or settings.app_public_url or "").rstrip("/")
    if not panel_url:
        panel_url = "http://localhost"

    try:
        await _do_install(
            job_id=job_id,
            server_id=server_id,
            node_name=node_name,
            location=location,
            panel_url=panel_url,
            force=force,
            initiated_by=initiated_by,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("install job=%s crashed", job_id)
        with session_scope() as db:
            job = db.get(NodeInstallJob, job_id)
            if job:
                job.status = "failed"
                job.error = str(exc)
                job.progress = 100
                job.finished_at = datetime.now(timezone.utc)


async def _do_install(
    *,
    job_id: int,
    server_id: int,
    node_name: str | None,
    location: str | None,
    panel_url: str,
    force: bool,
    initiated_by: int | None,
) -> None:
    # 1) Load server + mint a fresh node token.  The token is written to
    # the panel DB so future re-installs can re-use it without leaking
    # auth state to the remote host.
    with session_scope() as db:
        server = db.get(Server, server_id)
        if server is None:
            raise LookupError(f"server {server_id} disappeared")
        node_name = node_name or f"{server.name}-node"
        location = location or "external"
        token = issue_node_token(server.id, node_name=node_name, location=location)
        server.node_name = node_name
        server.node_location = location
        server.node_token = token
        server.node_install_started_at = datetime.now(timezone.utc)
        server.node_install_error = None
        server_status = server.status

    _set_status(job_id, "running", progress=5, message=f"probing {server_host(server_id)}")
    _append(job_id, f"→ panel_url={panel_url} node_name={node_name} location={location}")

    ssh = _build_client(server_id)
    try:
        await ssh.connect()
    except SSHError as exc:
        raise RuntimeError(f"ssh connect failed: {exc}") from exc

    try:
        # 2) Probe the host
        _set_status(job_id, "running", progress=10, message="detecting OS")
        os_info = await ssh.detect_os()
        pkg = await ssh.detect_package_manager()
        python_bin = await ssh.detect_python()
        _append(
            job_id,
            f"→ os={os_info.get('pretty')!r} pkg={pkg!r} python={python_bin!r} status={server_status}",
        )
        if not python_bin:
            raise RuntimeError("python3 not found on remote host")
        if pkg == "unknown":
            raise RuntimeError("no supported package manager found (need apt, dnf or yum)")

        _persist_meta(job_id, package_manager=pkg, os_info=os_info)

        # 3) (optional) tear down existing install on ``force``
        if force:
            _set_status(job_id, "running", progress=20, message="removing previous install")
            await _safe_uninstall(ssh, job_id)

        # 4) Install OS dependencies
        _set_status(job_id, "running", progress=30, message="installing system packages")
        await _install_packages(ssh, pkg, job_id)

        # 5) Upload node-agent tarball
        _set_status(job_id, "running", progress=55, message="uploading node-agent tarball")
        tar_path = await _build_tarball_locally(job_id)
        await ssh.upload_file(tar_path, "/tmp/nosrat-node.tar.gz")
        await ssh.run_command(
            "mkdir -p /opt/nosrat-node && tar -xzf /tmp/nosrat-node.tar.gz -C /opt/nosrat-node && "
            "rm -f /tmp/nosrat-node.tar.gz && ls -la /opt/nosrat-node",
            timeout=60,
        )

        # 6) Write config + systemd unit
        _set_status(job_id, "running", progress=75, message="configuring systemd unit")
        await _remote_install(ssh, job_id, panel_url=panel_url, token=token,
                              node_name=node_name, location=location, python_bin=python_bin)

        # 7) Wait for the agent to register
        _set_status(job_id, "running", progress=90, message="waiting for node to register")
        ok = await _wait_for_register(server_id, timeout=45.0)
        if not ok:
            raise RuntimeError("node did not register within timeout")

        with session_scope() as db:
            server = db.get(Server, server_id)
            if server is not None:
                server.node_installed = True
                server.node_install_completed_at = datetime.now(timezone.utc)
                server.node_install_error = None

        _set_status(job_id, "success", progress=100, message="node installed")
        _append(job_id, "✓ install complete")
    finally:
        await ssh.disconnect()

    _ = initiated_by  # currently unused; reserved for audit hook


def _build_client(server_id: int) -> SSHClient:
    """Construct an :class:`SSHClient` for ``server_id``.

    Resolution order for credentials:
      * SSH key uploaded into ``ssh_key_path`` column (path on the panel host)
      * Private key bytes stored in ``server_metadata['ssh_private_key']``
      * Password stored in ``server_metadata['ssh_password']``
    """
    with session_scope() as db:
        server = db.get(Server, server_id)
        if server is None:
            raise LookupError(f"server {server_id} not found")
        meta = server.server_metadata or {}
        key_path = server.ssh_key_path
        inline_key = meta.get("ssh_private_key")
        password = meta.get("ssh_password")
    return SSHClient(
        host=server_host(server_id),
        port=server_port(server_id),
        username=server_user(server_id),
        private_key_path=key_path,
        private_key=inline_key,
        password=password,
        connect_timeout=20.0,
    )


def server_host(server_id: int) -> str:
    with SessionLocal() as db:
        server = db.get(Server, server_id)
        if server is None:
            raise LookupError(server_id)
        return server.host


def server_port(server_id: int) -> int:
    with SessionLocal() as db:
        server = db.get(Server, server_id)
        if server is None:
            raise LookupError(server_id)
        return server.ssh_port


def server_user(server_id: int) -> str:
    with SessionLocal() as db:
        server = db.get(Server, server_id)
        if server is None:
            raise LookupError(server_id)
        return server.ssh_user


# ── Remote helpers ────────────────────────────────────────────────────────


async def _safe_uninstall(ssh: SSHClient, job_id: int) -> None:
    cmds = [
        "systemctl disable --now nosrat-node.service 2>/dev/null || true",
        "rm -rf /opt/nosrat-node /etc/nosrat-node",
        "rm -f /etc/systemd/system/nosrat-node.service",
        "systemctl daemon-reload",
    ]
    for cmd in cmds:
        try:
            result = await ssh.run_command(cmd, timeout=30)
            _append(job_id, f"  $ {cmd}\n    rc={result.returncode}")
        except SSHError as exc:
            _append(job_id, f"  $ {cmd}\n    error: {exc}")


async def _install_packages(ssh: SSHClient, pkg: str, job_id: int) -> None:
    cmds: list[str]
    if pkg == "apt-get":
        cmds = [
            "apt-get update -qq",
            "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-venv python3-pip ca-certificates curl",
        ]
    elif pkg in ("dnf", "yum"):
        cmds = [
            f"{pkg} -y install python3 python3-pip ca-certificates curl",
        ]
    else:
        raise RuntimeError(f"unsupported package manager: {pkg}")
    for cmd in cmds:
        _append(job_id, f"  $ {cmd}")
        result = await ssh.run_command(cmd, timeout=300)
        _append(job_id, f"    rc={result.returncode}")
        if result.stdout.strip():
            _append(job_id, "    " + result.stdout.strip().replace("\n", "\n    "))
        if not result.ok:
            raise RuntimeError(
                f"package install failed (rc={result.returncode}): {result.stderr.strip()}"
            )


async def _remote_install(
    ssh: SSHClient,
    job_id: int,
    *,
    panel_url: str,
    token: str,
    node_name: str,
    location: str,
    python_bin: str,
) -> None:
    # Create config dir + env file
    config = (
        f"PANEL_URL={panel_url}\n"
        f"NODE_TOKEN={token}\n"
        f"NODE_NAME={node_name}\n"
        f"NODE_LOCATION={location}\n"
        f"PYTHON_BIN={python_bin}\n"
    )
    await ssh.run_command("mkdir -p /etc/nosrat-node", timeout=10)
    await ssh.upload_text(config, "/etc/nosrat-node/config.env", mode=0o600)

    # venv
    _append(job_id, "  $ python3 -m venv /opt/nosrat-node/venv")
    result = await ssh.run_command(
        "python3 -m venv /opt/nosrat-node/venv", timeout=120
    )
    if not result.ok:
        raise RuntimeError(f"venv create failed: {result.stderr.strip()}")
    _append(job_id, "  $ /opt/nosrat-node/venv/bin/pip install -r /opt/nosrat-node/requirements.txt")
    result = await ssh.run_command(
        "/opt/nosrat-node/venv/bin/pip install -r /opt/nosrat-node/requirements.txt",
        timeout=600,
    )
    if not result.ok:
        raise RuntimeError(f"pip install failed: {result.stderr.strip()}")

    # systemd unit
    unit = _render_systemd_unit(user="root")
    await ssh.upload_text(unit, "/etc/systemd/system/nosrat-node.service", mode=0o644)

    # enable + start
    for cmd in (
        "systemctl daemon-reload",
        "systemctl enable nosrat-node.service",
        "systemctl restart nosrat-node.service",
    ):
        result = await ssh.run_command(cmd, timeout=30)
        _append(job_id, f"  $ {cmd}\n    rc={result.returncode}")


def _render_systemd_unit(*, user: str = "root") -> str:
    return f"""[Unit]
Description=nosrat-panel node agent
Documentation=https://github.com/pdnczone/Nosrat-Panel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
EnvironmentFile=/etc/nosrat-node/config.env
ExecStart=/opt/nosrat-node/venv/bin/python /opt/nosrat-node/agent.py
Restart=always
RestartSec=5
LimitNOFILE=65535
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""


async def _wait_for_register(server_id: int, *, timeout: float = 30.0) -> bool:
    """Poll the DB for ``node_last_seen`` to advance within ``timeout``."""
    deadline = time.monotonic() + timeout
    last_seen: datetime | None = None
    while time.monotonic() < deadline:
        with SessionLocal() as db:
            server = db.get(Server, server_id)
            if server is not None and server.node_status == "online":
                return True
            last_seen = server.node_last_seen if server else last_seen
        await asyncio.sleep(1.0)
    # Fall back to last-seen advancement
    with SessionLocal() as db:
        server = db.get(Server, server_id)
        return bool(server and server.node_last_seen and last_seen != server.node_last_seen)


# ── Local helpers ─────────────────────────────────────────────────────────


async def _build_tarball_locally(job_id: int) -> Path:
    """Bundle the ``node-agent/`` directory into a tar.gz in /tmp."""
    if not NODE_AGENT_DIR.is_dir():
        raise FileNotFoundError(f"node-agent directory missing: {NODE_AGENT_DIR}")

    out = Path(f"/tmp/nosrat-node-{job_id}-{int(time.time())}.tar.gz")
    _append(job_id, f"  bundling {NODE_AGENT_DIR} -> {out}")
    files = [
        "agent.py",
        "requirements.txt",
        "systemd",
        "install.sh",
        "uninstall.sh",
        "README.md",
        "nosrat-node",
    ]
    with tarfile.open(out, "w:gz") as tf:
        for name in files:
            src = NODE_AGENT_DIR / name
            if src.exists():
                tf.add(src, arcname=f"nosrat-node/{name}")
            else:
                _append(job_id, f"    (skipping missing {name})")
    return out


def _set_status(
    job_id: int, status: str, *, progress: int | None = None, message: str | None = None
) -> None:
    if message:
        _append(job_id, f"[{status}] {message}")
    with session_scope() as db:
        job = db.get(NodeInstallJob, job_id)
        if job is None:
            return
        job.status = status
        if progress is not None:
            job.progress = max(0, min(100, progress))
        if status in ("success", "failed", "cancelled"):
            job.finished_at = datetime.now(timezone.utc)
        if status == "success":
            job.progress = 100
            job.error = None


def _append(job_id: int, line: str) -> None:
    append_log(job_id, line)


def _persist_meta(job_id: int, *, package_manager: str, os_info: dict[str, Any]) -> None:
    with session_scope() as db:
        job = db.get(NodeInstallJob, job_id)
        if job is None:
            return
        job.package_manager = package_manager
        job.os_info = os_info