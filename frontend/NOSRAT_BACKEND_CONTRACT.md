# Nosrat Backend Contract

This document is the single source of truth for what the **Nosrat** frontend
expects from its backend. It is split into two parts:

1. **Existing endpoints** — already implemented by the current backend
   (inherited from the upstream Smite panel). Listed here for completeness
   and so the two sides of the project stay in sync.
2. **New endpoints (SSH Node Management)** — required by the new "Add Node
   via SSH" flow. **These are not implemented yet.** The frontend calls them
   for real; until the backend implements this contract, those calls will
   fail with a genuine network/HTTP error, and the UI shows that error
   honestly instead of faking success (see `NOSRAT_FRONTEND_CHANGELOG.md`,
   "Do NOT fake backend features").

All new endpoints are namespaced under `/nodes/ssh/*` and `/nodes/:id/*` so
they can be added incrementally without touching the existing CA-certificate
based registration flow, which continues to work unchanged.

---

## 1. Existing endpoints (already implemented)

| Method | Path | Used for |
|---|---|---|
| POST | `/auth/login` | Sign in |
| GET | `/auth/me` | Current session/user |
| GET | `/status` | Dashboard system + tunnel + node summary |
| GET | `/nodes` | List all nodes (Iran + foreign, filtered client-side by `metadata.role`) |
| POST | `/nodes` | Register a node (CA-certificate self-registration flow) |
| DELETE | `/nodes/:id` | Remove a node |
| POST | `/nodes/:id/restart` | Restart a node's agent |
| POST | `/nodes/:id/update` | Update a node's agent |
| POST | `/nodes/:id/reinstall` | Reinstall a node's agent |
| GET | `/panel/ca` / `/panel/ca?download=true` | Iran-node CA certificate (view / download) |
| GET | `/panel/ca/server` / `/panel/ca/server?download=true` | Foreign-server CA certificate (view / download) |
| GET / POST / DELETE | `/tunnels`, `/tunnels/:id` | Tunnel CRUD |
| POST | `/tunnels/:id/apply`, `/tunnels/reapply-all` | Apply tunnel config |
| GET | `/logs?limit=100` | Panel logs |
| GET | `/core-health/health` | Health of Backhaul/Rathole/Chisel/FRP cores |
| POST | `/core-health/reset/:core`, `/core-health/reset-config`, `/core-health/reset-config/:core` | Core reset actions |
| GET / PUT | `/settings` | Panel settings (FRP, Telegram bot, backups, tunnel auto-reapply) |

The frontend's `testExistingNodeConnection` (`POST /nodes/:id/test-connection`)
and `fetchNodeLogs` (`GET /nodes/:id/logs`) are called from the new Node
Details drawer's Actions/Logs tabs but **are not yet implemented** either —
they're grouped with the new contract below since they follow the same shape.

---

## 2. New endpoints — SSH Node Management (not implemented yet)

### 2.1 `POST /nodes/ssh/test-connection`

Validates that the panel can reach and authenticate to a candidate node
before installing anything.

**Request**
```json
{
  "name": "iran-node-2",
  "host": "203.0.113.10",
  "sshPort": 22,
  "username": "root",
  "authMethod": "password | private_key",
  "password": "string, present when authMethod = password",
  "private_key": "string, present when authMethod = private_key",
  "passphrase": "string, optional, only for private_key",
  "role": "iran | foreign"
}
```

**Success response — 200**
```json
{ "ok": true, "osFamily": "ubuntu", "osVersion": "24.04" }
```

**Error response — 400 / 401 / 504**
```json
{ "ok": false, "message": "Authentication failed" }
```
On the frontend, non-2xx responses are treated as a hard failure and shown
via the wizard's `ErrorState` (friendly message + collapsible technical
detail), never as a soft "ok: false".

**Frontend states:** loading spinner while testing → success card (with
detected OS) → or error card with "Try again".

---

### 2.2 `POST /nodes/ssh/install`

Starts the actual agent installation over SSH. Returns immediately with a
job id; installation itself is asynchronous.

**Request:** same shape as `test-connection`.

**Success response — 202**
```json
{ "jobId": "inst_8f2a1c", "nodeId": "optional, if pre-created" }
```

**Error response — 4xx/5xx**
```json
{ "detail": "human readable reason" }
```

**Frontend states:** "Install Node" button shows a loading spinner; on
success moves to the Progress step; on failure shows `ErrorState` with a
retry.

---

### 2.3 Install progress — real-time

Preferred: **WebSocket** at `/ws/nodes/install/:jobId`, one JSON message per
stage:

```json
{ "stage": "downloading", "message": "Downloading Nosrat Node…", "progressPercent": 45, "timestamp": "2026-09-12T10:00:00Z" }
```

Valid `stage` values (in order): `connecting`, `authenticating`,
`checking_os`, `checking_requirements`, `downloading`, `installing`,
`configuring`, `starting_service`, `verifying`, `completed`, `failed`.

Fallback: if the WebSocket can't be opened, the frontend polls
`GET /nodes/ssh/install/:jobId` every 2 seconds and expects the same JSON
shape as a single object (not an array).

**Frontend states:** animated progress bar + current stage label; `failed`
stage shows the message inline as an error with retry; `completed` moves to
the wizard's final "Node connected" screen.

---

### 2.4 `POST /nodes/:id/test-connection`

Re-checks reachability of an already-registered node (used by the Node
Details drawer's Actions tab, for both CA-registered and SSH-installed
nodes).

**Response:** same shape as 2.1.

---

### 2.5 `GET /nodes/:id/logs`

**Success response — 200**
```json
{ "lines": ["2026-09-12 10:00:00 INFO agent started", "..."] }
```

Used to power the Logs tab in the Node Details drawer (installation logs,
node logs, errors — the frontend currently renders these as one combined
list; splitting them into categories is a reasonable future backend
enhancement but not required for the contract to work).

---

### 2.6 Node resource reporting (extends `GET /nodes` or `GET /status`)

Not a new endpoint, but an extension to existing responses so the Node
Details drawer's Resources/Tunnel tabs can show live data instead of
"Requires agent support":

```json
{
  "resources": {
    "cpuPercent": 12.4,
    "memoryPercent": 38.1,
    "memoryUsedGb": 1.2,
    "memoryTotalGb": 4,
    "diskPercent": 55,
    "diskUsedGb": 22,
    "diskTotalGb": 40,
    "uptimeSeconds": 391922
  },
  "os": "Ubuntu 24.04",
  "installedVersion": "0.1.0"
}
```

The frontend's `mapApiNodeToView` (in `src/types/node.ts`) already reserves
these fields and will pick them up automatically once present — no frontend
change needed when this ships.

---

## Notes for backend implementation

- Never return `private_key` or `password` in any response — the frontend
  never persists them beyond the wizard's in-memory state and expects the
  backend to do the same (no logging, no echoing back).
- All new endpoints should require the same session auth as the rest of the
  panel (`Authorization` header handled by the existing `api` client).
- Prefer rejecting unimplemented endpoints with a normal 404/501 rather than
  timing out silently — the frontend already renders 404/501 as a clear
  "not supported yet" state.
