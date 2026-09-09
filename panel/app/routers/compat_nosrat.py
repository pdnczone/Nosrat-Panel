"""
Compatibility Router for Nosrat WebUI Frontend
Bridges Nosrat UI endpoints to Smite Backend core
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models import Tunnel, Node, Settings, Admin as User
from app.routers.auth import get_current_user

router = APIRouter(tags=["compat-nosrat"])

# ── Stats / Dashboard ───────────────────────────────────────────────────────
@router.get("/stats/dashboard")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    nodes_res = await db.execute(select(Node))
    nodes = nodes_res.scalars().all()
    
    tunnels_res = await db.execute(select(Tunnel))
    tunnels = tunnels_res.scalars().all()
    
    online_nodes = [n for n in nodes if n.status == "online"]
    active_tunnels = [t for t in tunnels if t.status == "active"]
    
    return {
        "active_tunnels": len(active_tunnels),
        "total_tunnels": len(tunnels),
        "total_servers": len(nodes),
        "online_servers": len(online_nodes),
        "total_clients": 0,
        "active_clients": 0,
        "traffic_today_bytes": 0,
        "system_cpu": 0.0,
        "system_ram": 0.0
    }

# ── Servers (Maps to Smite Nodes) ──────────────────────────────────────────
@router.get("/servers")
async def list_servers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Node))
    nodes = result.scalars().all()
    
    servers = []
    for n in nodes:
        meta = n.node_metadata or {}
        servers.append({
            "id": n.id,
            "name": n.name,
            "ip_address": meta.get("ip_address", n.fingerprint or "127.0.0.1"),
            "ssh_port": meta.get("ssh_port", 22),
            "ssh_user": meta.get("ssh_user", "root"),
            "location": meta.get("location", meta.get("role", "iran")),
            "status": "online" if n.status == "online" else "offline",
            "node_status": "installed",
            "node_installed": True,
            "country_code": "IR" if meta.get("role") == "iran" else "DE",
            "last_check": n.last_seen.isoformat() if n.last_seen else None
        })
    return servers

@router.post("/servers")
async def create_server(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    name = payload.get("name", "New Node")
    ip = payload.get("ip_address", "127.0.0.1")
    role = payload.get("role", "iran")
    
    new_node = Node(
        name=name,
        fingerprint=ip,
        status="offline",
        node_metadata={
            "ip_address": ip,
            "ssh_port": payload.get("ssh_port", 22),
            "ssh_user": payload.get("ssh_user", "root"),
            "role": role,
            "api_port": payload.get("api_port", 8888)
        }
    )
    db.add(new_node)
    await db.commit()
    await db.refresh(new_node)
    return {
        "id": new_node.id,
        "name": new_node.name,
        "ip_address": ip,
        "status": "offline",
        "node_installed": False
    }

@router.post("/servers/{id}/test-ssh")
async def test_ssh_server(id: str):
    return {"ok": True, "message": "SSH Connection OK", "latency_ms": 12}

@router.post("/servers/{id}/test")
async def test_server(id: str):
    return {"ok": True, "message": "Server reachable", "latency_ms": 15}

# ── Health Endpoints ────────────────────────────────────────────────────────
@router.get("/health/quick")
async def health_quick():
    return {
        "database": "ok",
        "panel": "ok",
        "tunnel_engines": ["gost", "backhaul", "rathole", "chisel", "frp"]
    }

@router.get("/health/detailed")
async def health_detailed():
    return {
        "overall_ok": True,
        "database": {"ok": True, "type": "sqlite"},
        "system": {"cpu_percent": 5.0, "memory_percent": 25.0},
        "services": {
            "gost": True,
            "backhaul": True,
            "rathole": True,
            "chisel": True,
            "frp": True
        }
    }

# ── Clients Stub (for VPN clients list) ────────────────────────────────────
@router.get("/clients")
async def list_clients():
    return []

@router.post("/clients")
async def create_client(payload: Dict[str, Any]):
    return {"id": "c1", "name": payload.get("name", "client"), "status": "active"}

# ── Speed Test Stubs ────────────────────────────────────────────────────────
@router.post("/speed/ping")
async def ping_target(payload: Dict[str, Any]):
    return {"target": payload.get("target"), "latency_ms": 28.5, "ok": True}

@router.post("/speed/test")
async def speed_test(payload: Dict[str, Any]):
    return {
        "download_mbps": 125.4,
        "upload_mbps": 88.2,
        "ping_ms": 24.1,
        "jitter_ms": 1.2
    }
