"""Async SSH client layer built on top of ``asyncssh``.

Used by the node installer and the interactive terminal WebSocket to run
commands and exchange files with remote ``nosrat`` nodes without blocking
the FastAPI event loop.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import asyncssh


logger = logging.getLogger("nosrat.ssh")


class SSHError(Exception):
    """Raised when an SSH operation fails. Wraps ``asyncssh`` errors."""

    def __init__(self, message: str, *, returncode: int | None = None, stderr: str = "") -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


@dataclass(slots=True)
class CommandResult:
    """The result of running a command over SSH."""

    command: str
    returncode: int
    stdout: str
    stderr: str
    duration_ms: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
        }


@dataclass(slots=True)
class StreamChunk:
    """A chunk of streaming output from a long-running SSH command."""

    stream: str  # "stdout" | "stderr"
    data: str
    timestamp: float = field(default_factory=time.time)


class SSHClient:
    """Async SSH client wrapper.

    Supports two authentication methods:

    * ``key``  – path to a private key on the panel host.
    * ``password`` – plaintext password (preferred via ``key``).

    Designed as a context manager that auto-disconnects on exit.
    """

    def __init__(
        self,
        host: str,
        port: int = 22,
        username: str = "root",
        *,
        private_key_path: str | None = None,
        private_key: str | None = None,
        password: str | None = None,
        client_keys: list[str] | None = None,
        connect_timeout: float = 15.0,
        known_hosts: asyncssh.SSHKnownHosts | None = None,
        keepalive_interval: int = 30,
    ) -> None:
        if not host:
            raise ValueError("host is required")
        if not username:
            raise ValueError("username is required")
        if not private_key_path and not private_key and not password and not client_keys:
            raise ValueError("one of private_key_path, private_key, password or client_keys is required")

        self.host = host
        self.port = port
        self.username = username
        self._private_key_path = private_key_path
        self._private_key = private_key
        self._password = password
        self._client_keys = client_keys
        self._connect_timeout = connect_timeout
        self._known_hosts = known_hosts  # None -> accept-new
        self._keepalive_interval = keepalive_interval
        self._conn: asyncssh.SSHClientConnection | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if self._conn is not None:
            return
        opts: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "known_hosts": self._known_hosts,  # None => accept-new
            "client_keys_none": False,
            "keepalive_interval": self._keepalive_interval,
            "config": None,
        }
        if self._private_key_path:
            opts["client_keys"] = [self._private_key_path]
        elif self._client_keys:
            opts["client_keys"] = self._client_keys
        elif self._private_key:
            opts["client_keys"] = [asyncssh.import_rsakey_from_string(self._private_key)]
        elif self._password:
            opts["password"] = self._password

        try:
            self._conn = await asyncio.wait_for(
                asyncssh.connect(**opts),
                timeout=self._connect_timeout,
            )
            logger.debug("ssh connected to %s@%s:%s", self.username, self.host, self.port)
        except asyncio.TimeoutError as exc:
            raise SSHError(f"ssh connect timeout after {self._connect_timeout}s") from exc
        except asyncssh.PermissionDenied as exc:
            raise SSHError(f"ssh auth failed: {exc}") from exc
        except (OSError, asyncssh.Error) as exc:
            raise SSHError(f"ssh connect failed: {exc}") from exc

    async def disconnect(self) -> None:
        if self._conn is None:
            return
        try:
            self._conn.close()
            await self._conn.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._conn = None

    async def __aenter__(self) -> "SSHClient":
        await self.connect()
        return self

    async def __aexit__(self, _exc_type, _exc, _tb) -> None:
        await self.disconnect()

    @property
    def connected(self) -> bool:
        return self._conn is not None

    # ── Commands ─────────────────────────────────────────────────────────

    async def run_command(
        self,
        command: str,
        *,
        timeout: float = 60.0,
        check: bool = False,
        input_data: str | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Run a single command and return its result.

        ``check=True`` raises ``SSHError`` on non-zero exit code.
        """
        if self._conn is None:
            raise SSHError("not connected")

        start = time.monotonic()
        try:
            proc = await self._conn.create_process(
                command,
                stderr=asyncssh.PIPE,
                stdout=asyncssh.PIPE,
                env=env or {},
            )
            try:
                if input_data is not None:
                    assert proc.stdin is not None
                    proc.stdin.write(input_data)
                    proc.stdin.write_eof()
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            finally:
                if proc.returncode is None:
                    proc.kill()
        except asyncio.TimeoutError as exc:
            raise SSHError(f"command timeout after {timeout}s: {command}") from exc
        except asyncssh.Error as exc:
            raise SSHError(f"ssh command failed: {exc}") from exc

        result = CommandResult(
            command=command,
            returncode=proc.returncode if proc.returncode is not None else -1,
            stdout=_decode(stdout_bytes),
            stderr=_decode(stderr_bytes),
            duration_ms=(time.monotonic() - start) * 1000.0,
        )
        if check and not result.ok:
            raise SSHError(
                f"command failed (rc={result.returncode}): {command}",
                returncode=result.returncode,
                stderr=result.stderr,
            )
        return result

    @asynccontextmanager
    async def stream_command(
        self,
        command: str,
        *,
        env: dict[str, str] | None = None,
        pty: bool = True,
        term_type: str = "xterm-256color",
        term_size: tuple[int, int, int, int] = (24, 80, 0, 0),
    ) -> AsyncIterator[asyncssh.SSHClientProcess]:
        """Stream stdout/stderr of a long-running command.

        Use ``proc.stdin.write(...)`` to feed input (e.g. an interactive shell).
        """
        if self._conn is None:
            raise SSHError("not connected")
        try:
            proc = await self._conn.create_process(
                command,
                stderr=asyncssh.PIPE,
                stdout=asyncssh.PIPE,
                env=env or {},
                term_type=term_type if pty else None,
                term_size=term_size if pty else None,
                encoding=None,
            )
        except asyncssh.Error as exc:
            raise SSHError(f"ssh stream failed: {exc}") from exc
        try:
            yield proc
        finally:
            if proc.returncode is None:
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass

    # ── File transfer ────────────────────────────────────────────────────

    async def upload_file(self, local_path: str | Path, remote_path: str) -> None:
        """Copy a local file to the remote host."""
        if self._conn is None:
            raise SSHError("not connected")
        local = Path(local_path)
        if not local.is_file():
            raise SSHError(f"local file not found: {local}")
        try:
            async with self._conn.start_sftp_client() as sftp:
                await sftp.put(str(local), remote_path)
        except asyncssh.Error as exc:
            raise SSHError(f"upload failed: {exc}") from exc

    async def upload_bytes(self, data: bytes, remote_path: str, *, mode: int = 0o755) -> None:
        """Write in-memory bytes to a remote file."""
        if self._conn is None:
            raise SSHError("not connected")
        try:
            async with self._conn.start_sftp_client() as sftp:
                async with sftp.open(remote_path, "wb") as f:
                    await f.write(data)
                await sftp.chmod(remote_path, mode)
        except asyncssh.Error as exc:
            raise SSHError(f"upload_bytes failed: {exc}") from exc

    async def upload_text(
        self,
        text: str,
        remote_path: str,
        *,
        mode: int = 0o755,
        encoding: str = "utf-8",
    ) -> None:
        await self.upload_bytes(text.encode(encoding), remote_path, mode=mode)

    async def download_file(self, remote_path: str, local_path: str | Path) -> None:
        if self._conn is None:
            raise SSHError("not connected")
        try:
            async with self._conn.start_sftp_client() as sftp:
                await sftp.get(remote_path, str(local_path))
        except asyncssh.Error as exc:
            raise SSHError(f"download failed: {exc}") from exc

    async def file_exists(self, remote_path: str) -> bool:
        if self._conn is None:
            raise SSHError("not connected")
        try:
            async with self._conn.start_sftp_client() as sftp:
                try:
                    await sftp.stat(remote_path)
                    return True
                except asyncssh.SFTPNoSuchFile:
                    return False
        except asyncssh.Error as exc:
            raise SSHError(f"stat failed: {exc}") from exc

    async def detect_package_manager(self) -> str:
        """Return ``apt``, ``dnf``, ``yum`` or ``unknown``."""
        for pm in ("apt-get", "dnf", "yum", "apk"):
            result = await self.run_command(f"command -v {pm}", timeout=5)
            if result.ok:
                return pm
        return "unknown"

    async def detect_os(self) -> dict[str, str]:
        """Return ``{id, version, pretty}`` from ``/etc/os-release``."""
        result = await self.run_command(
            "cat /etc/os-release 2>/dev/null || echo 'ID=unknown'",
            timeout=5,
        )
        info: dict[str, str] = {"id": "unknown", "version": "", "pretty": ""}
        for line in result.stdout.splitlines():
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if key == "ID":
                info["id"] = value.lower()
            elif key == "VERSION_ID":
                info["version"] = value
            elif key == "PRETTY_NAME":
                info["pretty"] = value
        return info

    async def detect_python(self) -> str:
        """Return absolute path to python3 (3.8+)."""
        for candidate in ("python3.12", "python3.11", "python3.10", "python3.9", "python3"):
            result = await self.run_command(f"command -v {candidate}", timeout=5)
            if result.ok and result.stdout.strip():
                return result.stdout.strip()
        return ""


def _decode(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    return data.decode("utf-8", errors="replace")