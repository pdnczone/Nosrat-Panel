# API Reference

Complete API documentation for nosrat-panel.

**Base URL**: `http://YOUR_SERVER/api/`
**WebSocket**: `ws://YOUR_SERVER/ws/`

---

## Authentication

All endpoints (except `/auth/login`) require a JWT token in the `Authorization` header:

```
Authorization: Bearer <your-jwt-token>
```

### Login

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin"
}
```

**Response 200**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### Get Current User

```http
GET /api/auth/me
Authorization: Bearer <token>
```

**Response 200**:
```json
{
  "id": 1,
  "username": "admin",
  "role": "admin",
  "is_active": true,
  "created_at": "2026-09-07T12:00:00",
  "last_login": "2026-09-07T13:00:00"
}
```

### Logout

```http
POST /api/auth/logout
Authorization: Bearer <token>
```

**Response 204**

---

## Servers

### List Servers

```http
GET /api/servers
```

**Response 200**:
```json
[
  {
    "id": 1,
    "name": "Iran-1",
    "host": "1.2.3.4",
    "ssh_port": 22,
    "ssh_user": "root",
    "status": "online",
    "last_seen": "2026-09-07T13:00:00",
    "nosrat_version": "2.0.0",
    "tunnel_count": 3
  }
]
```

### Create Server

```http
POST /api/servers
Content-Type: application/json

{
  "name": "Iran-1",
  "host": "1.2.3.4",
  "ssh_port": 22,
  "ssh_user": "root",
  "ssh_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n..."
}
```

### Get Server

```http
GET /api/servers/{id}
```

### Update Server

```http
PATCH /api/servers/{id}
```

### Delete Server

```http
DELETE /api/servers/{id}
```

### Test SSH Connection

```http
POST /api/servers/{id}/test
```

**Response 200**:
```json
{
  "success": true,
  "latency_ms": 45,
  "nosrat_version": "2.0.0"
}
```

---

## Tunnels

### List Tunnels

```http
GET /api/tunnels?server_id=1&type=gre_ipsec&status=active
```

**Query params**:
- `server_id` (optional)
- `type` (optional): plugin id
- `status` (optional): `active` | `inactive` | `error`

**Response 200**:
```json
[
  {
    "id": 1,
    "server_id": 1,
    "type": "gre_ipsec",
    "name": "iran-to-frankfurt",
    "params": {...},
    "config_path": "/etc/nosrat/tunnel.yaml",
    "status": "active",
    "created_at": "2026-09-07T12:00:00",
    "updated_at": "2026-09-07T13:00:00"
  }
]
```

### Create Tunnel

```http
POST /api/tunnels
Content-Type: application/json

{
  "server_id": 1,
  "type": "gre_ipsec",
  "name": "iran-to-frankfurt",
  "params": {
    "iran_ip": "1.1.1.1",
    "external_ip": "2.2.2.2",
    "use_psk": "256"
  }
}
```

**Response 201**:
```json
{
  "id": 1,
  "status": "created",
  "config_path": "/etc/nosrat/tunnel.yaml",
  "message": "Tunnel configuration created successfully"
}
```

### Get Tunnel

```http
GET /api/tunnels/{id}
```

### Update Tunnel

```http
PATCH /api/tunnels/{id}
```

### Delete Tunnel

```http
DELETE /api/tunnels/{id}
```

### Start Tunnel

```http
POST /api/tunnels/{id}/start
```

**Response 200**:
```json
{
  "success": true,
  "message": "Tunnel started"
}
```

### Stop Tunnel

```http
POST /api/tunnels/{id}/stop
```

### Restart Tunnel

```http
POST /api/tunnels/{id}/restart
```

### Get Tunnel Status

```http
GET /api/tunnels/{id}/status
```

**Response 200**:
```json
{
  "status": "active",
  "uptime_seconds": 3600,
  "traffic_in_bytes": 1234567,
  "traffic_out_bytes": 7654321,
  "latency_ms": 45,
  "packet_loss_pct": 0.0
}
```

### Get Tunnel Logs

```http
GET /api/tunnels/{id}/logs?lines=100
```

**Response 200**:
```json
{
  "logs": "2026-09-07 13:00:00 [INFO] Tunnel started\n..."
}
```

---

## Plugins

### List Plugins

```http
GET /api/plugins
```

**Response 200**:
```json
[
  {
    "id": "gre_ipsec",
    "name": "GRE-over-IPsec",
    "description": "Classic GRE tunnel with IPsec encryption",
    "version": "1.0.0",
    "icon": "🛡️"
  },
  {
    "id": "ghost_tunnel",
    "name": "Ghost Tunnel",
    "description": "WireGuard + Cloak + Nginx for DPI resistance",
    "version": "1.0.0",
    "icon": "👻"
  }
]
```

### Get Plugin Schema

```http
GET /api/plugins/{id}/schema
```

**Response 200**:
```json
{
  "title": "GRE-over-IPsec Iran Server",
  "fields": [
    {
      "key": "iran_ip",
      "label": "Iran Server Public IP",
      "type": "text",
      "required": true,
      "validation": "ipv4"
    }
  ]
}
```

---

## Crypto

### Generate PSK

```http
POST /api/crypto/psk/generate
Content-Type: application/json

{
  "bits": 256
}
```

**Response 200**:
```json
{
  "psk": "a3f2c8d9e1b4...",
  "bits": 256
}
```

### List PSKs

```http
GET /api/crypto/psk
```

### Get PSK (masked)

```http
GET /api/crypto/psk/{tunnel_id}
```

**Response 200**:
```json
{
  "tunnel_id": 1,
  "length": 64,
  "preview": "a3f2c8d9...b4c7e2f1",
  "created_at": "2026-09-07T12:00:00"
}
```

### Rotate PSK

```http
POST /api/crypto/psk/{tunnel_id}/rotate
Content-Type: application/json

{
  "bits": 256
}
```

### Change Algorithm

```http
PUT /api/crypto/algorithm
Content-Type: application/json

{
  "tunnel_id": 1,
  "algorithm": "aes256gcm16"
}
```

---

## Health

### Run Health Check

```http
POST /api/health/check
Content-Type: application/json

{
  "tunnel_id": 1,
  "mode": "quick"  // or "detailed"
}
```

**Response 200**:
```json
{
  "overall": "healthy",
  "checks": [
    {"name": "GRE interface", "status": "up", "details": "..."},
    {"name": "IPsec SA", "status": "up", "details": "..."},
    {"name": "Connectivity", "status": "up", "latency_ms": 45}
  ]
}
```

### Start Continuous Monitoring

```http
POST /api/health/monitor
Content-Type: application/json

{
  "tunnel_id": 1,
  "duration_seconds": 60,
  "interval_seconds": 5
}
```

Streams health check results via WebSocket.

---

## Speed Tests

### Ping Test

```http
POST /api/speed/ping
Content-Type: application/json

{
  "tunnel_id": 1,
  "count": 10
}
```

**Response 200**:
```json
{
  "min_ms": 42.1,
  "avg_ms": 45.3,
  "max_ms": 48.7,
  "packet_loss_pct": 0.0
}
```

### Full Speed Test

```http
POST /api/speed/test
Content-Type: application/json

{
  "tunnel_id": 1,
  "mode": "full"  // or "iperf"
}
```

### Get Test History

```http
GET /api/speed/history?server_id=1&days=7
```

---

## Users (Admin Only)

### List Users

```http
GET /api/users
```

### Create User

```http
POST /api/users
Content-Type: application/json

{
  "username": "operator1",
  "password": "strongpassword",
  "role": "operator"  // admin, operator, viewer
}
```

### Update User

```http
PATCH /api/users/{id}
```

### Delete User

```http
DELETE /api/users/{id}
```

### Change Password

```http
POST /api/users/{id}/change-password
Content-Type: application/json

{
  "new_password": "newstrongpassword"
}
```

---

## Settings

### Get All Settings

```http
GET /api/settings
```

### Update Setting

```http
PUT /api/settings
Content-Type: application/json

{
  "key": "session_timeout",
  "value": "3600"
}
```

---

## WebSocket Protocol

### Connect

```javascript
const ws = new WebSocket('ws://YOUR_SERVER/ws/status?token=YOUR_JWT_TOKEN');
```

### Subscribe to Tunnel Updates

```javascript
ws.send(JSON.stringify({
  "action": "subscribe",
  "channel": "tunnel_status",
  "tunnel_id": 1
}));
```

### Receive Updates

```javascript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // { "type": "tunnel_status", "tunnel_id": 1, "status": "active", "uptime": 3600 }
};
```

### Stream Live Logs

```javascript
const ws = new WebSocket('ws://YOUR_SERVER/ws/logs/1?token=YOUR_JWT_TOKEN');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // { "type": "log", "tunnel_id": 1, "line": "2026-09-07 13:00:00 [INFO] ..." }
};
```

---

## Error Responses

All errors return JSON in this format:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid input data",
    "details": {
      "field": "iran_ip",
      "issue": "Invalid IPv4 address"
    }
  }
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (success) |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 409 | Conflict (duplicate) |
| 422 | Unprocessable Entity |
| 429 | Too Many Requests (rate limited) |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

## Rate Limiting

- **API endpoints**: 100 requests per minute per IP
- **Login endpoint**: 5 attempts per minute per IP
- **WebSocket**: No limit (but connection timeout after 1h)

When rate limited, you'll get `429 Too Many Requests` with `Retry-After` header.

---

## Pagination

List endpoints support pagination:

```http
GET /api/tunnels?page=1&per_page=20
```

**Response**:
```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "per_page": 20,
  "pages": 3
}
```

---

## cURL Examples

### Login and Store Token

```bash
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' \
  | jq -r .access_token)

echo "Token: $TOKEN"
```

### List Tunnels

```bash
curl -s http://localhost/api/tunnels \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Create Tunnel

```bash
curl -s -X POST http://localhost/api/tunnels \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "server_id": 1,
    "type": "gre_ipsec",
    "name": "my-tunnel",
    "params": {
      "iran_ip": "1.1.1.1",
      "external_ip": "2.2.2.2"
    }
  }' | jq
```

### Start Tunnel

```bash
curl -s -X POST http://localhost/api/tunnels/1/start \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## SDK / Client Libraries

Coming soon:
- Python SDK
- Go SDK
- JavaScript/TypeScript SDK

For now, use the REST API directly from your language of choice.
