# nosrat-panel

<div align="center">

**Modern, macOS-inspired tunnel management panel for nosrat**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Svelte 5](https://img.shields.io/badge/Svelte-5-FF3E00.svg)](https://svelte.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6.svg)](https://www.typescriptlang.org/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.4-38B2AC.svg)](https://tailwindcss.com/)

---

🛡️ **GRE-over-IPsec** • 👻 **Ghost Tunnel** • 🔌 **Plugin System**

[Features](#-features) • [Quick Start](#-quick-start) • [Documentation](docs/) • [Screenshots](#-screenshots)

</div>

---

## ✨ Features

- 🎨 **macOS-inspired UI** - Glass morphism, SF Pro typography, traffic lights, smooth animations
- 🔌 **Plugin System** - Add new tunnel types without modifying core (WireGuard, OpenVPN, custom protocols)
- 🌍 **Multi-Server** - Manage tunnels across multiple remote servers from a single panel
- 📡 **Real-time Updates** - WebSocket-based live status monitoring
- 🔐 **JWT Authentication** - Secure, role-based access control (admin/operator/viewer)
- 🌐 **Bilingual** - Full Persian (RTL) + English (LTR) support
- 📊 **Live Metrics** - Real-time traffic, latency, and health monitoring
- 🛠️ **Built-in Tunnel Types**:
  - **GRE-over-IPsec** - Classic GRE tunnel with IKEv2/ESP encryption
  - **Ghost Tunnel** - WireGuard + Cloak + Nginx (DPI-resistant)
- 🔍 **Health Checks** - Quick check, detailed diagnosis, continuous monitoring
- 🚄 **Speed Tests** - Ping latency, throughput, iperf3
- 🔑 **Crypto Management** - PSK generation (256/512-bit), rotation, algorithm change
- 🌓 **Dark + Light Mode** - macOS-style theming
- 📱 **Responsive** - Works on desktop, tablet, mobile
- 🐳 **Docker-ready** - systemd service with security hardening

---

## 🚀 Quick Start

### One-line install

```bash
sudo bash -c "$(curl -sL https://raw.githubusercontent.com/pdnczone/nosrat-panel/main/setup.sh)"
```

### Manual install

```bash
git clone https://github.com/pdnczone/nosrat-panel.git
cd nosrat-panel
sudo bash setup.sh
```

Access: `http://YOUR_SERVER_IP/`
Default credentials: `admin` / `admin` (change immediately!)

---

## 📦 What's Included

```
nosrat-panel/
├── backend/          # FastAPI + SQLAlchemy + JWT (4,543 lines, 38 files)
│   ├── api/         # REST endpoints + WebSocket
│   ├── core/        # config, security, subprocess, plugin loader
│   ├── db/          # SQLAlchemy models + schemas + migrations
│   └── plugins/     # gre_ipsec, ghost_tunnel, wireguard_native
├── frontend/         # Svelte 5 + Vite + Tailwind (3,855 lines, 38 files)
│   ├── src/lib/     # api, auth, ws, theme, i18n, components
│   ├── src/routes/  # 12 pages (Login, Dashboard, Tunnels, etc.)
│   └── public/      # locales (fa, en), favicon
├── systemd/          # systemd service + nginx config (hardened)
├── docs/             # Installation, User Guide, Plugin Dev, API, Security
├── setup.sh          # 7-step idempotent installer
└── README.md         # this file
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (WebUI)                          │
│         Svelte 5 + Tailwind + macOS-inspired                │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTPS / WSS
┌──────────────────────┴───────────────────────────────────────┐
│                      Nginx (Reverse Proxy)                    │
│              /api/*  →  FastAPI  (port 8000)                 │
│              /ws     →  WebSocket (port 8000)                │
│              /       →  Static frontend (dist/)              │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────┴───────────────────────────────────────┐
│                FastAPI Backend (Python)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   API Layer  │  │ AI / Crypto  │  │   Plugins    │      │
│  │   (REST+WS)  │  │   Services   │  │  (gre_ipsec, │      │
│  │              │  │              │  │   ghost, ...) │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         └──────────────────┴──────────────────┘              │
│                    ┌──────────────┐                          │
│                    │  Repositories│                          │
│                    └──────┬───────┘                          │
│                           │                                  │
│                    ┌──────┴───────┐                          │
│                    │   SQLite    │                          │
│                    └──────────────┘                          │
└──────────────────────┬───────────────────────────────────────┘
                       │ SSH / subprocess
┌──────────────────────┴───────────────────────────────────────┐
│              Remote Servers (nosrat nodes)                    │
│         /etc/nosrat/ + nosrat CLI + tunnels                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Installation](docs/INSTALLATION.md) | Detailed setup, SSL/HTTPS, troubleshooting |
| [User Guide](docs/USER_GUIDE.md) | Bilingual (fa + en) - Login, servers, tunnels, health, speed, users |
| [Plugin Development](docs/PLUGIN_DEVELOPMENT.md) | Create your own tunnel type |
| [API Reference](docs/API.md) | REST endpoints + WebSocket protocol |
| [Security](docs/SECURITY.md) | JWT, bcrypt, HTTPS, rate limiting, threat model |

---

## 🔌 Plugin System

Add a new tunnel type in 3 steps:

1. **Create plugin folder**: `backend/plugins/my_tunnel/`
2. **Write `manifest.json`** (metadata)
3. **Write `wizard_schema.json`** (UI form fields)
4. **Implement `plugin.py`** (extends `PluginBase`)

The frontend **auto-discovers** your plugin and renders the wizard form from your schema.

Example: see `backend/plugins/wireguard_native/` for a minimal plugin.

---

## 🛠️ Development

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev  # http://localhost:5173
```

### Running tests

```bash
cd backend
pytest
```

---

## 🐛 Troubleshooting

```bash
# Backend logs
sudo journalctl -u nosrat-panel-backend -f

# Nginx logs
sudo tail -f /var/log/nginx/error.log

# Restart everything
sudo systemctl restart nosrat-panel-backend nginx
```

---

## 📜 License

MIT © [PDNC](https://github.com/pdnczone)

---

## 💖 Credits

- Built with [FastAPI](https://fastapi.tiangolo.com/), [Svelte 5](https://svelte.dev/), [TailwindCSS](https://tailwindcss.com/)
- UI inspired by [macOS Sonoma](https://www.apple.com/macos/sonoma/)
- Part of the [nosrat](https://github.com/pdnczone/nosrat) ecosystem

---

## 🔗 Related

- [nosrat](https://github.com/pdnczone/nosrat) - The CLI tunnel manager this panel controls
- [Heshmat](https://github.com/pdnczone/Heshmat) - Telegram support bot

---

<div align="center">

📺 [YouTube: @PDNC30](https://youtube.com/@PDNC30) • 📢 [Telegram: @PDNCzone](https://t.me/PDNCzone) • 💬 [Support](https://t.me/dncdirect)

</div>
