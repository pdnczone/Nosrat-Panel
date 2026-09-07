# Node Agent API Reference

This document covers the new HTTP / WebSocket surface introduced for the
``nosrat-node`` agent integration.  All paths are relative to the panel
base URL (default ``/api``).

## Authentication

| Audience            | Auth mechanism                                       |
|---------------------|------------------------------------------------------|
| WebUI / operators   | JWT issued by ``/api/auth/login`` (``type=access``)  |
| Node agents         | JWT minted via ``core.agent_auth.issue_node_token``  |

Node JWTs carry:
* ``type=node``
* ``server_id`` – the ``servers.id`` they belong to
* ``node_name``, ``location``
* ``scopes`` – includes ``server:<id>`` plus capability flags

## REST endpoints

### Servers (extended)

| Method | Path                                              | Description                              | Auth   |
|--------|---------------------------------------------------|------------------------------------------|--------|
| POST   | `/api/servers`                                    | Create server (now accepts inline key/password) | user |
| GET    | `/api/servers`                                    | List servers (includes node fields)      | user   |
| GET    | `/api/servers/{id}`                               | Get one server                           | user   |
| PATCH  | `/api/servers/{id}`                               | Update credentials / node metadata       | user   |
| DELETE | `/api/servers/{id}`                               | Delete server                            | user   |
| POST   | `/api/servers/{id}/test`                          | ICMP/SSH legacy probe                    | user   |
| POST   | `/api/servers/{id}/test-ssh`                      | asyncssh live probe                      | user   |
| POST   | `/api/servers/{id}/install-node`                  | Start node install (background)          | admin  |
| GET    | `/api/servers/{id}/install-status?after_line=N`   | Tail install log                         | user   |
| GET    | `/api/servers/{id}/node-info`                     | Combined server + node info              | user   |

### Nodes (new module `/api/nodes`)

| Method | Path                                            | Description                              | Auth |
|--------|-------------------------------------------------|------------------------------------------|------|
| GET    | `/api/nodes`                                    | List all servers with node info          | user |
| GET    | `/api/nodes/{id}`                               | Single node                              | user |
| POST   | `/api/nodes/{id}/command`                       | Push a command (returns 202 + ack)       | user |
| GET    | `/api/nodes/{id}/metrics?since_minutes=N&limit=M` | History of metric samples              | user |
| GET    | `/api/nodes/{id}/metrics/latest`                | Last sample                              | user |
| GET    | `/api/nodes/{id}/logs?since_minutes=N&limit=M`  | Cached log lines                         | user |
| GET    | `/api/nodes/{id}/commands?limit=N`              | Command audit history                    | user |

## WebSocket endpoints

### `/ws/agent` — node → panel

Auth: `?token=<node-jwt>` (or `Authorization: Bearer <token>`).

Agent → panel messages:

```jsonc
{"type": "register", "id": "...", "payload": {
    "node_id": "...", "version": "1.0.0",
    "hostname": "...", "location": "iran",
    "os": {"system": "Linux", "kernel": "..."},
    "interfaces": [{"name": "eth0", "ipv4": ["1.2.3.4"], ...}]
}}

{"type": "metrics", "payload": {
    "cpu_percent": 12.5, "ram_percent": 45.0, "ram_used_mb": 4096,
    "ram_total_mb": 8192, "disk_percent": 30.0, "disk_used_gb": 12.4,
    "network_rx_bytes": 123456, "network_tx_bytes": 789012,
    "load_avg_1m": 0.4, "load_avg_5m": 0.5, "load_avg_15m": 0.4,
    "uptime_seconds": 86400, "hostname": "node-1", "extra": {}
}}

{"type": "log", "payload": {
    "level": "info", "source": "agent", "message": "..."
}}

{"type": "command_result", "id": "<command_id>", "payload": {
    "status": "success", "stdout": "...", "stderr": "...",
    "exit_code": 0
}}

{"type": "pong"}
```

Panel → agent messages:

```jsonc
{"type": "registered", "id": "...", "payload": {"server_id": 1, "ok": true}}
{"type": "ping", "ts": 1234567890}
{"type": "command", "id": "<command_id>", "payload": {
    "command": "tunnel start 5",
    "args": {"--flag": true},
    "timeout": 60
}}
{"type": "update", "payload": {"agent_url": "https://..."}}
```

### `/api/servers/{id}/terminal` — operator SSH proxy

Auth: JWT via `?token=` or `Authorization`.

Proxies an interactive `bash -l` shell on the remote host to the
browser through xterm.js.  Send `RESIZE:rowsxcols` text frames to resize
the remote PTY.

### `/api/nodes/ws` — operator fan-out

Auth: user access JWT.

Emits `{"type": "node_snapshot", "ts": ..., "nodes": [...]}` every 2s
with a snapshot of currently-connected agents (server_id, hostname,
uptime, etc.).

## Code map

```
backend/
├── core/
│   ├── ssh.py              async SSH client wrapper (asyncssh)
│   ├── agent_auth.py       Node JWT issuance & validation
│   ├── agent_bus.py        In-process registry of agent WebSockets
│   └── config.py           + node_agent_dir, node_install_timeout_sec, app_public_url
├── db/
│   ├── models.py           + Server.node_* + NodeMetric + NodeCommand + NodeInstallJob + NodeLog
│   ├── schemas.py          + NodeInfo / NodeMetricIn/Out / NodeCommand* / NodeLog* / WSEnvelope / ServerNodeOut
│   └── migrations.py       + _backfill_node_defaults
├── services/
│   ├── __init__.py
│   └── node_installer.py   Background job: SSH → detect OS → apt/dnf → tarball → systemd
└── api/
    ├── servers.py          + test-ssh, install-node, install-status, terminal, node-info
    ├── nodes.py            /api/nodes CRUD + ingestion helpers (record_metric, record_log, …)
    └── ws.py               + /ws/agent (node protocol) + /api/nodes/ws (operator fan-out)

node-agent/
├── agent.py                Daemon: WS client + local HTTP API + metrics sampler
├── install.sh              Curl|bash installer (cross-platform)
├── uninstall.sh            Removes service + files
├── nosrat-node             Local CLI for in-host API
├── requirements.txt        psutil + websockets + aiohttp + pyjwt
├── systemd/nosrat-node.service
└── README.md

frontend/src/
├── lib/
│   ├── api.js              + ServersAPI.{testSSH, installNode, installStatus, nodeInfo, terminalUrl}
│   │                       + NodesAPI.*
│   ├── components/
│   │   ├── Terminal.svelte       xterm.js wrapper (RESIZE frames, dynamic import)
│   │   └── InstallProgress.svelte Live install log viewer
│   └── stores/nodes.js     nodes + nodeEvents + startNodeEventStream()
├── routes/
│   ├── Servers.svelte      Add/edit/delete + Test SSH + Install Node + Terminal modals
│   └── Nodes.svelte        Live metrics + terminal + command runner + logs
└── App.svelte              + /nodes route
```

## Operational notes

* **Cross-platform install**: `install.sh` detects apt / dnf / yum / apk
  and Python ≥ 3.8.
* **Idempotent**: re-running the installer refreshes files and the venv.
  Pass `--force` to wipe the venv first.
* **Token rotation**: each install mints a fresh node JWT.  Tokens carry
  `server:<id>` scope so a leaked token cannot impersonate another node.
* **Logs are bounded**: `NodeInstallJob.log` is capped at 64 KiB; older
  lines are dropped.
* **WebSocket auth is checked twice**: (a) JWT signature / scope at
  accept, (b) `server_id` claim is validated against the URL path for
  any future per-resource WS routes.
* **Recovery from panel restart**: the agent auto-reconnects with
  exponential back-off (configurable via `WS_RECONNECT_MIN` /
  `WS_RECONNECT_MAX`).
* **SSH terminal proxy** binds via asyncssh PTY (term_type
  `xterm-256color`), supports `RESIZE:` control frames sent from the
  browser.