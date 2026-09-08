#!/usr/bin/env python3
"""nosrat-node — the lightweight agent that runs on every managed host.

Responsibilities
----------------
* Open an outbound WebSocket to ``$PANEL_URL/ws/agent`` (authenticated with
  ``$NODE_TOKEN``) and keep it alive with exponential-backoff reconnect.
* Periodically sample host metrics (``psutil``) and stream them to the panel.
* Receive ``command`` messages and reply with ``command_result``.
* Expose a tiny local HTTP API on ``127.0.0.1:$NODE_LOCAL_PORT`` (default
  9000) so the on-host ``nosrat-node`` CLI can inspect / trigger actions
  without going through the panel.

Configuration (all via env vars in ``/etc/nosrat-node/config.env``)
-------------------------------------------------------------------
* ``PANEL_URL``      — base URL of the panel (no trailing slash).
* ``NODE_TOKEN``     — JWT minted by the panel's ``issue_node_token``.
* ``NODE_NAME``      — human-friendly name (``iran-1``, ``external-2`` …).
* ``NODE_LOCATION``  — ``iran`` | ``external``.
* ``NODE_LOCAL_PORT``— local API port (default 9000).
* ``METRICS_INTERVAL``— seconds between samples (default 5).
* ``WS_RECONNECT_MIN/MAX`` — reconnect backoff bounds (default 1/30 s).
* ``LOG_LEVEL``      — DEBUG / INFO / WARNING / ERROR (default INFO).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import socket
import sys
import time
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

import aiohttp
import psutil
from aiohttp import web
from aiohttp import WSMsgType


# ── Configuration ──────────────────────────────────────────────────────────

PANEL_URL: str = os.environ.get("PANEL_URL", "").rstrip("/")
NODE_TOKEN: str = os.environ.get("NODE_TOKEN", "")
NODE_NAME: str = os.environ.get("NODE_NAME", socket.gethostname())
NODE_LOCATION: str = os.environ.get("NODE_LOCATION", "external")
NODE_LOCAL_PORT: int = int(os.environ.get("NODE_LOCAL_PORT", "9000"))
METRICS_INTERVAL: float = float(os.environ.get("METRICS_INTERVAL", "5"))
WS_RECONNECT_MIN: float = float(os.environ.get("WS_RECONNECT_MIN", "1"))
WS_RECONNECT_MAX: float = float(os.environ.get("WS_RECONNECT_MAX", "30"))
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()
AGENT_VERSION = "1.1.0"
AGENT_DIR = Path(__file__).resolve().parent
TUNNEL_CONFIG_DIR = Path("/etc/nosrat-tunnels")
TUNNEL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("nosrat-node")


# ── Metrics collection ────────────────────────────────────────────────────


def _safe_disk_usage(path: str = "/") -> tuple[float, float]:
    try:
        u = psutil.disk_usage(path)
        return float(u.percent), round(u.used / (1024 ** 3), 2)
    except Exception:  # noqa: BLE001
        return 0.0, 0.0


def _net_io() -> tuple[int, int]:
    try:
        io = psutil.net_io_counters()
        return int(io.bytes_recv), int(io.bytes_sent)
    except Exception:  # noqa: BLE001
        return 0, 0


def collect_metrics() -> dict[str, Any]:
    cpu = psutil.cpu_percent(interval=None)
    vm = psutil.virtual_memory()
    disk_pct, disk_used_gb = _safe_disk_usage()
    rx, tx = _net_io()
    try:
        load1, load5, load15 = (float(x) for x in psutil.getloadavg())
    except (AttributeError, OSError):
        load1 = load5 = load15 = 0.0
    try:
        uptime = int(time.time() - psutil.boot_time())
    except Exception:  # noqa: BLE001
        uptime = 0
    return {
        "cpu_percent": float(cpu),
        "ram_percent": float(vm.percent),
        "ram_used_mb": int(vm.used / (1024 * 1024)),
        "ram_total_mb": int(vm.total / (1024 * 1024)),
        "disk_percent": disk_pct,
        "disk_used_gb": disk_used_gb,
        "network_rx_bytes": rx,
        "network_tx_bytes": tx,
        "load_avg_1m": load1,
        "load_avg_5m": load5,
        "load_avg_15m": load15,
        "uptime_seconds": uptime,
        "hostname": socket.gethostname(),
        "extra": {},
    }


# ── Agent core ────────────────────────────────────────────────────────────


class NodeAgent:
    """Stateful WebSocket client + local HTTP server."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_task: asyncio.Task[None] | None = None
        self._metrics_task: asyncio.Task[None] | None = None
        self._local_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._last_metric: dict[str, Any] | None = None
        self._registered = asyncio.Event()
        self._interfaces = _interfaces()

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        self._configure_logging()
        self._validate_config()
        logger.info(
            "starting nosrat-node %s name=%s location=%s panel=%s",
            AGENT_VERSION, NODE_NAME, NODE_LOCATION, PANEL_URL,
        )
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, connect=30),
            headers={"user-agent": f"nosrat-node/{AGENT_VERSION}"},
        )
        # Prime cpu_percent so the first sample is meaningful
        psutil.cpu_percent(interval=None)
        self._ws_task = asyncio.create_task(self._ws_loop(), name="ws-loop")
        self._metrics_task = asyncio.create_task(self._metrics_loop(), name="metrics-loop")
        self._local_task = asyncio.create_task(self._local_api(), name="local-api")
        await self._stop.wait()
        await self.shutdown()

    async def shutdown(self) -> None:
        logger.info("shutting down")
        for task in (self._ws_task, self._metrics_task, self._local_task):
            if task and not task.done():
                task.cancel()
        if self._ws is not None and not self._ws.closed:
            with suppress(Exception):
                await self._ws.close()
        if self._session is not None:
            await self._session.close()

    # ── WebSocket loop ────────────────────────────────────────────────

    async def _ws_loop(self) -> None:
        backoff = WS_RECONNECT_MIN
        session = self._session
        assert session is not None
        while not self._stop.is_set():
            try:
                url = f"{PANEL_URL}/ws/agent?token={NODE_TOKEN}"
                logger.info("connecting to %s", PANEL_URL)
                async with session.ws(url, autoclose=False, autoping=True) as ws:
                    self._ws = ws
                    backoff = WS_RECONNECT_MIN
                    await self._send_register(ws)
                    async for msg in ws:
                        if msg.type == WSMsgType.TEXT:
                            await self._handle_message(json.loads(msg.data))
                        elif msg.type == WSMsgType.ERROR:
                            logger.warning("ws error: %s", ws.exception())
                            break
                        elif msg.type == WSMsgType.CLOSE:
                            logger.info("ws closed by server (code=%s)", msg.data)
                            break
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("ws disconnected: %s (retry in %.1fs)", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(WS_RECONNECT_MAX, backoff * 2)
            finally:
                self._ws = None
                self._registered.clear()

    async def _send_register(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        uname = _safe_uname()
        payload = {
            "type": "register",
            "id": uuid.uuid4().hex,
            "payload": {
                "node_id": f"{socket.gethostname()}-{uuid.uuid4().hex[:6]}",
                "version": AGENT_VERSION,
                "hostname": socket.gethostname(),
                "location": NODE_LOCATION,
                "os": uname,
                "interfaces": self._interfaces,
            },
        }
        await ws.send_json(payload)
        logger.info("sent register; awaiting ack")

    # ── Metrics loop ──────────────────────────────────────────────────

    async def _metrics_loop(self) -> None:
        while not self._stop.is_set():
            try:
                sample = await asyncio.to_thread(collect_metrics)
                self._last_metric = sample
                if self._registered.is_set() and self._ws is not None:
                    await self._ws.send_json(
                        {"type": "metrics", "payload": sample}
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("metrics loop error: %s", exc)
            await asyncio.sleep(METRICS_INTERVAL)

    # ── Inbound message handler ──────────────────────────────────────

    async def _handle_message(self, msg: dict[str, Any]) -> None:
        mtype = msg.get("type")
        if mtype == "registered":
            self._registered.set()
            logger.info("panel acknowledged registration")
            return
        if mtype == "ping":
            if self._ws is not None:
                await self._ws.send_json({"type": "pong"})
            return
        if mtype == "command":
            asyncio.create_task(self._execute_command(msg))
            return
        if mtype == "apply_tunnel_config":
            asyncio.create_task(self._handle_apply_tunnel_config(msg))
            return
        if mtype == "start_tunnel":
            asyncio.create_task(self._handle_start_tunnel(msg))
            return
        if mtype == "stop_tunnel":
            asyncio.create_task(self._handle_stop_tunnel(msg))
            return
        if mtype == "tunnel_status":
            asyncio.create_task(self._handle_tunnel_status(msg))
            return
        if mtype == "destroy_tunnel":
            asyncio.create_task(self._handle_destroy_tunnel(msg))
            return
        if mtype == "update":
            asyncio.create_task(self._self_update(msg))
            return
        if mtype == "error":
            logger.error("panel error: %s", msg.get("payload"))
            return
        logger.debug("unhandled message type=%r", mtype)

    async def _execute_command(self, msg: dict[str, Any]) -> None:
        command_id = msg.get("id") or uuid.uuid4().hex
        payload = msg.get("payload") or {}
        command = payload.get("command") or ""
        args = payload.get("args") or {}
        timeout = int(payload.get("timeout", 60))
        logger.info("exec command_id=%s command=%s", command_id, command)
        try:
            proc = await asyncio.create_subprocess_shell(
                _build_shell_command(command, args),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                result = {
                    "command_id": command_id,
                    "status": "failed",
                    "stdout": "",
                    "stderr": f"timeout after {timeout}s",
                    "exit_code": 124,
                }
            else:
                result = {
                    "command_id": command_id,
                    "status": "success" if proc.returncode == 0 else "failed",
                    "stdout": stdout_b.decode("utf-8", errors="replace"),
                    "stderr": stderr_b.decode("utf-8", errors="replace"),
                    "exit_code": proc.returncode,
                }
        except Exception as exc:  # noqa: BLE001
            result = {
                "command_id": command_id,
                "status": "failed",
                "stdout": "",
                "stderr": f"exec error: {exc}",
                "exit_code": -1,
            }
        if self._ws is not None:
            await self._ws.send_json(
                {"type": "command_result", "id": command_id, "payload": result}
            )

    # ── Tunnel config / lifecycle handlers ──────────────────────────────

    def _send_tunnel_reply(self, msg: dict[str, Any], payload: dict[str, Any]) -> None:
        """Send a reply for tunnel commands (use the message 'id' as command_id)."""
        if self._ws is not None:
            command_id = msg.get("id") or uuid.uuid4().hex
            asyncio.create_task(
                self._ws.send_json(
                    {"type": "command_result", "id": command_id, "payload": payload}
                )
            )

    async def _handle_apply_tunnel_config(self, msg: dict[str, Any]) -> None:
        """Write the tunnel config file and install any required packages."""
        payload = msg.get("payload") or {}
        plugin = payload.get("plugin", "")
        config = payload.get("config", {})
        tunnel_id = config.get("tunnel_id") or payload.get("tunnel_id") or 0
        logger.info("apply_tunnel_config plugin=%s tunnel_id=%s", plugin, tunnel_id)

        try:
            # Persist the config to disk
            cfg_path = TUNNEL_CONFIG_DIR / f"{plugin}-{tunnel_id}.json"
            cfg_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
            cfg_path.chmod(0o600)

            # Install required packages based on plugin type
            if plugin == "gre_ipsec":
                ret = await self._run_subprocess(
                    "apt-get update -qq && apt-get install -y -qq strongswan iproute2 || "
                    "yum install -y strongswan iproute || dnf install -y strongswan iproute",
                    timeout=300,
                )
                if ret.get("exit_code") != 0:
                    logger.warning("package install warning: %s", ret.get("stderr"))
            elif plugin == "wireguard_native":
                ret = await self._run_subprocess(
                    "apt-get install -y -qq wireguard wireguard-tools || "
                    "yum install -y wireguard-tools || dnf install -y wireguard-tools",
                    timeout=300,
                )
                if ret.get("exit_code") != 0:
                    logger.warning("wg install warning: %s", ret.get("stderr"))

            self._send_tunnel_reply(msg, {
                "status": "success",
                "stdout": f"config written to {cfg_path}",
                "stderr": "",
                "exit_code": 0,
            })
        except Exception as exc:  # noqa: BLE001
            logger.exception("apply_tunnel_config failed")
            self._send_tunnel_reply(msg, {
                "status": "failed",
                "stdout": "",
                "stderr": str(exc),
                "exit_code": -1,
            })

    async def _handle_start_tunnel(self, msg: dict[str, Any]) -> None:
        """Start the tunnel: bring up GRE interface, IPsec SA, or wg-quick."""
        payload = msg.get("payload") or {}
        plugin = payload.get("plugin", "")
        tunnel_id = payload.get("tunnel_id") or 0
        logger.info("start_tunnel plugin=%s tunnel_id=%s", plugin, tunnel_id)

        try:
            if plugin == "gre_ipsec":
                await self._run_subprocess(
                    "systemctl enable --now strongswan 2>/dev/null; systemctl enable --now ipsec 2>/dev/null; true",
                    timeout=60,
                )
                # Read config to determine GRE addresses
                cfg_path = self._find_config(plugin, tunnel_id)
                iran_gre = "10.200.0.1/30"
                external_gre = "10.200.0.2/30"
                local_public = ""
                remote_public = ""
                if cfg_path and cfg_path.exists():
                    cfg = json.loads(cfg_path.read_text())
                    iran_gre = cfg.get("iran", {}).get("gre_ip", iran_gre)
                    external_gre = cfg.get("external", {}).get("gre_ip", external_gre)
                    local_public = cfg.get("iran", {}).get("public_ip", "")
                    remote_public = cfg.get("external", {}).get("public_ip", "")

                # Determine if we are the Iran side or external side based on
                # which public_ip matches this host's addresses.
                is_iran = self._is_this_host(local_public)
                gre_ip = iran_gre if is_iran else external_gre
                peer_ip = external_gre if is_iran else iran_gre
                remote_pub = remote_public if is_iran else local_public

                # Configure GRE tunnel
                await self._run_subprocess(
                    f"ip link add gre0 type gre remote {remote_pub} local {local_public if is_iran else remote_public} ttl 255",
                    timeout=10,
                )
                await self._run_subprocess(
                    f"ip addr add {gre_ip} dev gre0",
                    timeout=10,
                )
                await self._run_subprocess("ip link set gre0 up", timeout=10)
                # IPsec stronglyswan config
                await self._write_ipsec_config(tunnel_id, gre_ip, peer_ip, remote_pub)
                await self._run_subprocess("ipsec restart", timeout=30)

            elif plugin == "wireguard_native":
                interface = f"wg{tunnel_id}"
                await self._run_subprocess(f"wg-quick up {interface}", timeout=60)

            elif plugin == "ghost_tunnel":
                for unit in ("wg-quick@wg0", "cloak-client", "nginx"):
                    await self._run_subprocess(f"systemctl start {unit}", timeout=30)

            self._send_tunnel_reply(msg, {
                "status": "success",
                "stdout": "tunnel started",
                "stderr": "",
                "exit_code": 0,
            })
        except Exception as exc:  # noqa: BLE001
            logger.exception("start_tunnel failed")
            self._send_tunnel_reply(msg, {
                "status": "failed",
                "stdout": "",
                "stderr": str(exc),
                "exit_code": -1,
            })

    async def _handle_stop_tunnel(self, msg: dict[str, Any]) -> None:
        """Stop the tunnel."""
        payload = msg.get("payload") or {}
        plugin = payload.get("plugin", "")
        tunnel_id = payload.get("tunnel_id") or 0
        logger.info("stop_tunnel plugin=%s tunnel_id=%s", plugin, tunnel_id)

        try:
            if plugin == "gre_ipsec":
                await self._run_subprocess("ip link set gre0 down", timeout=10)
                await self._run_subprocess("ip link del gre0", timeout=10)
                await self._run_subprocess("ipsec stop", timeout=30)
            elif plugin == "wireguard_native":
                interface = f"wg{tunnel_id}"
                await self._run_subprocess(f"wg-quick down {interface}", timeout=60)
            elif plugin == "ghost_tunnel":
                for unit in ("wg-quick@wg0", "cloak-client", "nginx"):
                    await self._run_subprocess(f"systemctl stop {unit}", timeout=30)

            self._send_tunnel_reply(msg, {
                "status": "success",
                "stdout": "tunnel stopped",
                "stderr": "",
                "exit_code": 0,
            })
        except Exception as exc:  # noqa: BLE001
            logger.exception("stop_tunnel failed")
            self._send_tunnel_reply(msg, {
                "status": "failed",
                "stdout": "",
                "stderr": str(exc),
                "exit_code": -1,
            })

    async def _handle_tunnel_status(self, msg: dict[str, Any]) -> None:
        """Report real tunnel status from this endpoint."""
        payload = msg.get("payload") or {}
        plugin = payload.get("plugin", "")
        tunnel_id = payload.get("tunnel_id") or 0

        try:
            if plugin == "gre_ipsec":
                gre_r = await self._run_subprocess("ip link show gre0", timeout=10)
                ipsec_r = await self._run_subprocess("ipsec status 2>&1 | head -40", timeout=10)
                gre_up = gre_r.get("exit_code") == 0
                ipsec_out = ipsec_r.get("stdout", "")
                sa_up = "INSTALLED" in ipsec_out or "ESTABLISHED" in ipsec_out
                status = "up" if (gre_up and sa_up) else "down"
                self._send_tunnel_reply(msg, {
                    "status": status,
                    "gre_up": gre_up,
                    "ipsec_established": sa_up,
                    "stdout": f"gre_up={gre_up} | ipsec_sa={sa_up}",
                    "stderr": "",
                    "exit_code": 0,
                })
            elif plugin == "wireguard_native":
                interface = f"wg{tunnel_id}"
                r = await self._run_subprocess(f"wg show {interface}", timeout=10)
                if r.get("exit_code") != 0:
                    self._send_tunnel_reply(msg, {
                        "status": "down",
                        "stdout": r.get("stdout", ""),
                        "stderr": r.get("stderr", ""),
                        "exit_code": r.get("exit_code", 1),
                    })
                else:
                    # Parse transfer stats
                    transfer_rx = transfer_tx = 0
                    for line in r.get("stdout", "").splitlines():
                        if "transfer:" in line:
                            parts = line.split()
                            for i, part in enumerate(parts):
                                if part == "received,":
                                    transfer_rx = _parse_bytes(parts[i - 1])
                                elif part == "sent":
                                    transfer_tx = _parse_bytes(parts[i - 1])
                    self._send_tunnel_reply(msg, {
                        "status": "up",
                        "traffic_in_bytes": transfer_rx,
                        "traffic_out_bytes": transfer_tx,
                        "stdout": r.get("stdout", ""),
                        "stderr": "",
                        "exit_code": 0,
                    })
            elif plugin == "ghost_tunnel":
                statuses = {}
                for unit in ("wg-quick@wg0", "cloak-client", "nginx"):
                    r = await self._run_subprocess(
                        f"systemctl is-active {unit}", timeout=10
                    )
                    statuses[unit] = r.get("stdout", "").strip()
                all_active = all(v == "active" for v in statuses.values())
                self._send_tunnel_reply(msg, {
                    "status": "up" if all_active else "down",
                    "units": statuses,
                    "stdout": json.dumps(statuses),
                    "stderr": "",
                    "exit_code": 0,
                })
            else:
                self._send_tunnel_reply(msg, {
                    "status": "unknown",
                    "stderr": f"unknown plugin: {plugin}",
                    "exit_code": 1,
                    "stdout": "",
                })
        except Exception as exc:  # noqa: BLE001
            logger.exception("tunnel_status failed")
            self._send_tunnel_reply(msg, {
                "status": "error",
                "stderr": str(exc),
                "exit_code": -1,
                "stdout": "",
            })

    async def _handle_destroy_tunnel(self, msg: dict[str, Any]) -> None:
        """Remove tunnel configuration files and bring everything down."""
        payload = msg.get("payload") or {}
        plugin = payload.get("plugin", "")
        tunnel_id = payload.get("tunnel_id") or 0
        try:
            await self._handle_stop_tunnel(msg)
            cfg = self._find_config(plugin, tunnel_id)
            if cfg and cfg.exists():
                cfg.unlink(missing_ok=True)
            self._send_tunnel_reply(msg, {
                "status": "success",
                "stdout": "destroyed",
                "stderr": "",
                "exit_code": 0,
            })
        except Exception as exc:  # noqa: BLE001
            self._send_tunnel_reply(msg, {
                "status": "failed",
                "stderr": str(exc),
                "exit_code": -1,
                "stdout": "",
            })

    def _find_config(self, plugin: str, tunnel_id: int) -> Path | None:
        """Look up the config file for a plugin+tunnel combination."""
        if not TUNNEL_CONFIG_DIR.exists():
            return None
        candidates = [
            TUNNEL_CONFIG_DIR / f"{plugin}-{tunnel_id}.json",
            TUNNEL_CONFIG_DIR / f"{plugin}-{tunnel_id}.conf",
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    def _is_this_host(self, ip: str) -> bool:
        """Heuristic: check if an IP matches any local interface address."""
        if not ip:
            return True  # cannot determine — assume local
        try:
            addrs: set[str] = set()
            for iface_addrs in psutil.net_if_addrs().values():
                for a in iface_addrs:
                    addrs.add(a.address)
        except Exception:  # noqa: BLE001
            addrs = set()
        return ip in addrs or ip == "127.0.0.1"

    async def _write_ipsec_config(self, tunnel_id: int, local_gre: str, peer_gre: str, remote_pub: str) -> None:
        """Write strongSwan ipsec.conf + ipsec.secrets for a GRE-over-IPsec tunnel."""
        conn_name = f"gre-{tunnel_id}"
        local_gre_ip = local_gre.split("/")[0]
        peer_gre_ip = peer_gre.split("/")[0]

        conf = f"""conn {conn_name}
    type=transport
    keyexchange=ikev2
    left=%defaultroute
    leftprotoport=47
    right={remote_pub}
    rightprotoport=47
    auto=add
"""
        secrets = f"# PSK for {conn_name}\n: PSK \"{self._read_psk(tunnel_id)}\"\n"
        try:
            Path("/etc/ipsec.conf").write_text(conf, encoding="utf-8")
            Path("/etc/ipsec.secrets").write_text(secrets, encoding="utf-8")
        except OSError as exc:
            logger.warning("could not write ipsec config: %s", exc)
            raise RuntimeError(f"could not write ipsec config: {exc}") from exc

    def _read_psk(self, tunnel_id: int) -> str:
        """Read the PSK from a tunnel config file."""
        try:
            cfg_path = self._find_config("gre_ipsec", tunnel_id)
            if cfg_path and cfg_path.exists():
                cfg = json.loads(cfg_path.read_text())
                return str(cfg.get("psk", ""))
        except Exception:  # noqa: BLE001
            pass
        return ""

    async def _self_update(self, msg: dict[str, Any]) -> None:
        """Trigger a self-update: download the latest ``agent.py`` and restart."""
        payload = msg.get("payload") or {}
        url = payload.get("agent_url")
        if not url:
            url = f"{PANEL_URL.replace('/api', '')}/raw/main/node-agent/agent.py"
        session = self._session
        if session is None:
            logger.warning("self_update skipped: no HTTP session")
            return
        try:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.read()
            current = AGENT_DIR / "agent.py"
            backup = AGENT_DIR / "agent.py.bak"
            backup.write_bytes(current.read_bytes())
            current.write_bytes(data)
            current.chmod(0o644)
        except Exception as exc:  # noqa: BLE001
            logger.error("self_update download failed: %s", exc)
            return
        logger.info("agent.py updated; restarting")
        os.execvp(sys.executable, [sys.executable, str(AGENT_DIR / "agent.py")])

    # ── Local HTTP API ────────────────────────────────────────────────

    async def _local_api(self) -> None:
        app = web.Application()
        app.router.add_get("/status", self._http_status)
        app.router.add_get("/metrics", self._http_metrics)
        app.router.add_get("/health", self._http_health)
        app.router.add_post("/run", self._http_run)
        app.router.add_post("/self-update", self._http_self_update)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", NODE_LOCAL_PORT)
        await site.start()
        logger.info("local API listening on 127.0.0.1:%s", NODE_LOCAL_PORT)
        try:
            await self._stop.wait()
        finally:
            await runner.cleanup()

    async def _http_status(self, _request: web.Request) -> web.Response:
        return web.json_response(
            {
                "agent": "nosrat-node",
                "version": AGENT_VERSION,
                "node_name": NODE_NAME,
                "node_location": NODE_LOCATION,
                "panel_url": PANEL_URL,
                "registered": self._registered.is_set(),
                "ws_open": self._ws is not None and not self._ws.closed,
            }
        )

    async def _http_metrics(self, _request: web.Request) -> web.Response:
        if self._last_metric is None:
            self._last_metric = await asyncio.to_thread(collect_metrics)
        return web.json_response(self._last_metric)

    async def _http_health(self, _request: web.Request) -> web.Response:
        return web.json_response(
            {
                "ok": True,
                "uptime": int(time.time() - psutil.boot_time()),
                "load": psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0.0, 0.0, 0.0),
            }
        )

    async def _http_run(self, request: web.Request) -> web.Response:
        body = await request.json()
        command = body.get("command", "")
        if not command:
            return web.json_response({"error": "command required"}, status=400)
        result = await self._run_subprocess(command, timeout=int(body.get("timeout", 60)))
        return web.json_response(result)

    async def _http_self_update(self, _request: web.Request) -> web.Response:
        if self._ws is None:
            return web.json_response({"ok": False, "error": "ws offline"}, status=503)
        await self._ws.send_json({"type": "update", "payload": {}})
        return web.json_response({"ok": True})

    async def _run_subprocess(self, command: str, *, timeout: int) -> dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "stdout": stdout_b.decode("utf-8", errors="replace"),
                "stderr": stderr_b.decode("utf-8", errors="replace"),
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {"error": f"timeout after {timeout}s", "exit_code": 124}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc), "exit_code": -1}

    # ── Helpers ───────────────────────────────────────────────────────

    def _validate_config(self) -> None:
        missing = []
        if not PANEL_URL:
            missing.append("PANEL_URL")
        if not NODE_TOKEN:
            missing.append("NODE_TOKEN")
        if missing:
            raise SystemExit(
                f"missing required env vars: {', '.join(missing)} "
                "(set them in /etc/nosrat-node/config.env)"
            )

    def _configure_logging(self) -> None:
        logging.basicConfig(
            level=LOG_LEVEL,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            stream=sys.stderr,
        )


def _build_shell_command(command: str, args: dict[str, Any]) -> str:
    """Render ``command`` + ``args`` into a safe-ish shell string.

    The panel only sends commands it generated, so this is best-effort
    escaping for arbitrary string arguments.  Operators should prefer
    whitelisted command names (``status``, ``reload`` …) instead of
    fully free-form shell.
    """
    if not args:
        return command
    pieces = [command]
    for k, v in args.items():
        if not isinstance(k, str) or not k.replace("-", "").replace("_", "").isalnum():
            continue
        if isinstance(v, bool):
            if v:
                pieces.append(f"--{k}")
        elif isinstance(v, (int, float)):
            pieces.append(f"--{k}={v}")
        else:
            pieces.append(f"--{k}={_shq(str(v))}")
    return " ".join(pieces)


def _shq(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _safe_uname() -> dict[str, str]:
    import os as _os
    import platform

    info = {
        "system": platform.system(),
        "release": platform.release(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
    }
    try:
        u = _os.uname()
        info["release"] = u.release
        info["kernel"] = u.release
        info["machine"] = u.machine
    except (AttributeError, OSError):
        pass
    return info


def _interfaces() -> list[dict[str, Any]]:
    """Snapshot of network interfaces (best-effort)."""
    out: list[dict[str, Any]] = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    for name in stats:
        entry: dict[str, Any] = {
            "name": name,
            "is_up": stats[name].isup,
            "speed_mbps": stats[name].speed,
            "mtu": stats[name].mtu,
        }
        for addr in addrs.get(name, []):
            key = "ipv4" if addr.family == 2 else "ipv6" if addr.family == 10 else f"family_{addr.family}"
            entry.setdefault(key, []).append(addr.address)
        out.append(entry)
    return out


def _parse_bytes(size_str: str) -> int:
    """Parse a size string like '1.23 MiB' to bytes."""
    units = {
        "B": 1,
        "KiB": 1024,
        "MiB": 1024 ** 2,
        "GiB": 1024 ** 3,
        "TiB": 1024 ** 4,
    }
    parts = size_str.split()
    if len(parts) != 2:
        return 0
    try:
        value = float(parts[0])
        unit = parts[1]
        return int(value * units.get(unit, 1))
    except (ValueError, KeyError):
        return 0


# ── CLI entry ─────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="nosrat-node")
    parser.add_argument("--panel-url", default=os.environ.get("PANEL_URL"))
    parser.add_argument("--token", default=os.environ.get("NODE_TOKEN"))
    parser.add_argument("--name", default=os.environ.get("NODE_NAME"))
    parser.add_argument("--location", default=os.environ.get("NODE_LOCATION"))
    parser.add_argument("--local-port", type=int, default=int(os.environ.get("NODE_LOCAL_PORT", "9000")))
    parser.add_argument("--metrics-interval", type=float, default=float(os.environ.get("METRICS_INTERVAL", "5")))
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"))
    parser.add_argument("--once", action="store_true", help="send a single metrics sample and exit")
    return parser.parse_args()


def _apply_args(args: argparse.Namespace) -> None:
    global PANEL_URL, NODE_TOKEN, NODE_NAME, NODE_LOCATION
    global NODE_LOCAL_PORT, METRICS_INTERVAL, LOG_LEVEL
    if args.panel_url:
        PANEL_URL = args.panel_url.rstrip("/")
    if args.token:
        NODE_TOKEN = args.token
    if args.name:
        NODE_NAME = args.name
    if args.location:
        NODE_LOCATION = args.location
    NODE_LOCAL_PORT = args.local_port
    METRICS_INTERVAL = args.metrics_interval
    LOG_LEVEL = args.log_level.upper()


async def _run() -> None:
    agent = NodeAgent()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, agent._stop.set)
    if "--once" in sys.argv:
        sample = await asyncio.to_thread(collect_metrics)
        print(json.dumps(sample, indent=2))
        return
    await agent.start()


def main() -> None:
    args = _parse_args()
    _apply_args(args)
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()