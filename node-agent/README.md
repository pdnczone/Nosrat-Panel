# nosrat-node

Lightweight Python daemon installed on every managed host (Iran/foreign)
that the nosrat WebUI panel orchestrates.  Communicates with the panel
over a single authenticated WebSocket, runs commands on demand, and
streams host metrics + logs back in real time.

## Repository layout

```
node-agent/
├── nosrat-node              # Local CLI (talks to the in-host API on :9000)
├── agent.py                 # Daemon: WS client + HTTP API + metrics sampler
├── requirements.txt         # Pinned runtime deps
├── install.sh               # Curl|bash one-liner installer
├── uninstall.sh             # Removes service + files
├── systemd/nosrat-node.service
└── README.md                # You are here
```

## Configuration

`/etc/nosrat-node/config.env` (mode 0600) is written by `install.sh`:

| Variable             | Description                                              |
|----------------------|----------------------------------------------------------|
| `PANEL_URL`          | Panel base URL (e.g. `https://panel.example.com`)        |
| `NODE_TOKEN`         | JWT minted by the panel (carries `type=node` claim)      |
| `NODE_NAME`          | Operator-chosen label (`iran-1`, `external-2` …)         |
| `NODE_LOCATION`      | `iran` or `external`                                     |
| `PYTHON_BIN`         | Path to the venv's python (managed by installer)         |
| `NODE_LOCAL_PORT`    | Port for in-host API (default `9000`)                    |
| `METRICS_INTERVAL`   | Seconds between metric samples (default `5`)             |
| `WS_RECONNECT_MIN/MAX` | Backoff bounds when reconnecting (default `1`/`30`)     |
| `LOG_LEVEL`          | `DEBUG` / `INFO` / `WARN` / `ERROR` (default `INFO`)     |

## Installation

The panel triggers the install via SSH; the same flow can be reproduced
manually:

```bash
curl -sL https://raw.githubusercontent.com/pdnczone/Nosrat-Panel/main/node-agent/install.sh | \
    sudo bash -s -- \
        --panel-url=https://panel.example.com \
        --token=eyJhbGciOi... \
        --name=iran-1 \
        --location=iran
```

The installer is idempotent: re-running it refreshes the venv, files and
service unit.  Pass `--force` to wipe the existing venv first.

## Operating

```bash
# Inspect local state
nosrat-node status

# Tail in-memory metric sample
nosrat-node metrics

# Run an arbitrary shell command (logged + audit)
nosrat-node run "ip route"

# Trigger self-update via the panel
nosrat-node self-update
```

## WebSocket protocol

Frames are JSON-encoded.  See the panel's
[`/root/nosrat-panel/backend/api/ws.py`](../backend/api/ws.py) and
[`/root/nosrat-panel/backend/core/agent_bus.py`](../backend/core/agent_bus.py)
for the full schema.  The short version:

### agent → panel

```json
{"type": "register",       "id": "...", "payload": { ... }}
{"type": "metrics",        "payload": { "cpu_percent": 12.5, ... }}
{"type": "log",            "payload": { "level": "info", "message": "..." }}
{"type": "command_result", "id": "<command_id>", "payload": { ... }}
{"type": "pong"}
```

### panel → agent

```json
{"type": "command", "id": "...", "payload": { "command": "...", "args": {...}, "timeout": 60 }}
{"type": "ping"}
{"type": "update",  "payload": { "agent_url": "..." }}
```

## Security

* Tokens carry the `type=node` claim and `server:<id>` scope.
* The local HTTP API binds to `127.0.0.1` only.
* The systemd unit runs as root by default; tighten `User=` if needed.
* Config file mode is `0600`, install directory `0755`.
* The installer refuses to run as a non-root user without `sudo`.

## Supported platforms

* Ubuntu 20.04+
* Debian 11+
* RHEL/Rocky/Alma 8+
* Fedora 36+
* Any distro with `python3.8+`, `apt`, `dnf`, `yum` or `apk`