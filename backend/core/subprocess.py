"""Safe subprocess execution wrapper for invoking the nosrat CLI / binary."""
from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.config import settings


logger = logging.getLogger("nosrat.subprocess")


class CommandError(Exception):
    """Raised when a subprocess invocation fails."""

    def __init__(
        self,
        message: str,
        *,
        returncode: int | None = None,
        stdout: str = "",
        stderr: str = "",
        command: Sequence[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.command = list(command) if command else []


@dataclass(slots=True)
class CommandResult:
    """The result of a successful subprocess invocation."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
        }


def _resolve_cmd(cmd: Sequence[str]) -> list[str]:
    """Make sure the executable exists; raise if not."""
    if not cmd:
        raise CommandError("empty command")
    head = cmd[0]
    if "/" in head or head.startswith("."):
        if not Path(head).exists():
            raise CommandError(f"executable not found: {head}")
        return list(cmd)
    resolved = shutil.which(head)
    if resolved is None:
        raise CommandError(f"command not found on PATH: {head}")
    return [resolved, *cmd[1:]]


def _cmd_to_str(cmd: Sequence[str]) -> str:
    try:
        return shlex.join(cmd)
    except AttributeError:  # py < 3.8
        return " ".join(shlex.quote(p) for p in cmd)


async def run(
    cmd: Sequence[str],
    *,
    timeout: float | None = None,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    input_data: str | bytes | None = None,
    check: bool = False,
) -> CommandResult:
    """Run an external command asynchronously with a hard timeout."""
    full_cmd = _resolve_cmd(cmd)
    timeout = timeout if timeout is not None else settings.command_timeout_sec
    loop = asyncio.get_running_loop()
    started = loop.time()

    logger.debug("subprocess.start cmd=%s timeout=%s", _cmd_to_str(full_cmd), timeout)

    proc = await asyncio.create_subprocess_exec(
        *full_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env={**os.environ, **env} if env is not None else None,
    )

    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(
                input=input_data.encode() if isinstance(input_data, str) else input_data
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise CommandError(
            f"command timed out after {timeout}s: {_cmd_to_str(full_cmd)}",
            returncode=None,
            command=full_cmd,
        ) from exc

    duration_ms = (loop.time() - started) * 1000.0
    result = CommandResult(
        command=full_cmd,
        returncode=proc.returncode if proc.returncode is not None else -1,
        stdout=stdout_b.decode(errors="replace") if stdout_b else "",
        stderr=stderr_b.decode(errors="replace") if stderr_b else "",
        duration_ms=round(duration_ms, 2),
    )

    if check and result.returncode != 0:
        raise CommandError(
            f"command failed (rc={result.returncode}): {_cmd_to_str(full_cmd)}",
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            command=full_cmd,
        )

    logger.debug(
        "subprocess.end cmd=%s rc=%s duration_ms=%s",
        _cmd_to_str(full_cmd),
        result.returncode,
        result.duration_ms,
    )
    return result


async def run_shell(
    command: str,
    *,
    timeout: float | None = None,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = False,
) -> CommandResult:
    """Run a shell string via `/bin/sh -c`."""
    return await run(
        ["/bin/sh", "-c", command],
        timeout=timeout,
        cwd=cwd,
        env=env,
        check=check,
    )


async def run_nosrat(
    *args: str,
    timeout: float | None = None,
    check: bool = False,
    use_cli: bool = False,
) -> CommandResult:
    """Run the nosrat binary (or bash CLI) with the given positional args."""
    binary = settings.nosrat_cli if use_cli else settings.nosrat_bin
    return await run(
        [binary, *args],
        timeout=timeout,
        check=check,
    )