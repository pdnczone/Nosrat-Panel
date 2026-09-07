# Installation Guide

Complete installation guide for nosrat-panel.

---

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 22.04/24.04, Debian 12+, RHEL 9+, Rocky 9+
- **RAM**: 1GB minimum, 2GB recommended
- **Disk**: 500MB for application + dependencies
- **Network**: Ports 80 (HTTP) and 443 (HTTPS) accessible

### Software Requirements (auto-installed by setup.sh)
- Python 3.11+
- Node.js 18+ and npm
- Nginx
- Certbot (for HTTPS)
- Git, curl, jq, openssl

---

## 🚀 Quick Install (Recommended)

```bash
sudo bash -c "$(curl -sL https://raw.githubusercontent.com/pdnczone/nosrat-panel/main/setup.sh)"
```

The installer will:
1. ✅ Detect your OS and package manager
2. ✅ Install all dependencies
3. ✅ Create `/opt/nosrat-panel` directory
4. ✅ Set up Python venv
5. ✅ Build the frontend
6. ✅ Install and enable systemd service
7. ✅ Configure nginx
8. ✅ Start everything

After install, access the panel at:
```
http://YOUR_SERVER_IP/
```

**Default credentials**: `admin` / `admin` (change immediately!)

---

## 📦 Manual Install

```bash
# 1. Clone the repository
git clone https://github.com/pdnczone/nosrat-panel.git
cd nosrat-panel

# 2. Install system dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nodejs npm \
    nginx certbot python3-certbot-nginx git curl jq openssl

# 3. Run the installer
sudo bash setup.sh
```

---

## 🔒 Enable HTTPS (Recommended for Production)

### Option 1: Using a Domain

```bash
# Point your domain's A record to the server IP first
sudo certbot --nginx -d panel.yourdomain.com
```

Certbot will automatically:
- Obtain an SSL certificate from Let's Encrypt
- Modify the nginx config to use HTTPS
- Set up auto-renewal

### Option 2: Using IP Only (Self-Signed)

```bash
# Generate self-signed cert
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/nosrat.key \
    -out /etc/nginx/ssl/nosrat.crt \
    -subj "/CN=YOUR_SERVER_IP"

# Edit nginx config (/etc/nginx/sites-available/nosrat-panel)
# Uncomment the HTTPS server block and the HTTP->HTTPS redirect
# Update ssl_certificate paths
```

---

## 🔧 Post-Install Configuration

### 1. Change Default Admin Password

1. Login with `admin` / `admin`
2. Go to **Settings** → **Users**
3. Click on your user
4. Set a strong password

### 2. Add a Remote Server

1. Go to **Servers** in the sidebar
2. Click **+ Add Server**
3. Fill in:
   - **Name**: e.g., "Iran-1"
   - **Host**: IP address or hostname
   - **SSH Port**: 22
   - **SSH User**: root
   - **SSH Key**: Paste your private key
4. Click **Test Connection** to verify
5. Click **Save**

### 3. Install nosrat on the Remote Server

The panel can manage remote servers, but each server must have nosrat installed:

```bash
# On the remote server
curl -sL https://raw.githubusercontent.com/pdnczone/nosrat/main/install.sh | sudo bash
```

### 4. Create Your First Tunnel

1. Go to **Tunnels** → **+ Create Tunnel**
2. Select a tunnel type (e.g., GRE-over-IPsec)
3. Select a server
4. Fill in the wizard form
5. Click **Create**
6. Use the **Start** button to activate

---

## 🔄 Updating

```bash
# Pull latest code
cd /opt/nosrat-panel
sudo git pull

# Reinstall dependencies and rebuild
cd /opt/nosrat-panel
sudo bash setup.sh
```

The installer is **idempotent** - it can be run multiple times safely.

---

## 🗑️ Uninstallation

```bash
# Stop and disable service
sudo systemctl stop nosrat-panel-backend
sudo systemctl disable nosrat-panel-backend

# Remove systemd unit
sudo rm /etc/systemd/system/nosrat-panel-backend.service
sudo systemctl daemon-reload

# Remove nginx config
sudo rm /etc/nginx/sites-enabled/nosrat-panel
sudo rm /etc/nginx/sites-available/nosrat-panel
sudo systemctl reload nginx

# Remove application files
sudo rm -rf /opt/nosrat-panel

# Optional: remove logs
sudo rm -rf /var/log/nosrat-panel
```

---

## 🐛 Troubleshooting

### Backend won't start

```bash
# Check logs
sudo journalctl -u nosrat-panel-backend -n 50

# Common issues:
# 1. Port 8000 already in use
sudo lsof -i :8000

# 2. Python venv not found
ls -la /opt/nosrat-panel/venv/bin/

# 3. Database permission issues
sudo chown -R root:root /opt/nosrat-panel
```

### Frontend not loading (502 Bad Gateway)

```bash
# Check if backend is running
sudo systemctl status nosrat-panel-backend

# Check nginx config
sudo nginx -t

# Restart services
sudo systemctl restart nosrat-panel-backend nginx
```

### Cannot login

```bash
# Reset admin password
cd /opt/nosrat-panel
source venv/bin/activate
python3 -c "
import sys
sys.path.insert(0, 'backend')
from core.security import hash_password
from db.database import SessionLocal
from db.models import User
from sqlalchemy import select

db = SessionLocal()
admin = db.execute(select(User).where(User.username == 'admin')).scalar_one_or_none()
if admin:
    admin.password_hash = hash_password('newpassword')
    db.commit()
    print('Password reset to: newpassword')
else:
    print('Admin user not found')
"
```

### Plugin not loading

```bash
# Check plugin manifest is valid
python3 -c "import json; json.load(open('/opt/nosrat-panel/backend/plugins/my_tunnel/manifest.json'))"

# Check plugin has all required files
ls /opt/nosrat-panel/backend/plugins/my_tunnel/
# Should contain: __init__.py, plugin.py, manifest.json, wizard_schema.json

# Restart backend
sudo systemctl restart nosrat-panel-backend
```

### Port 80 already in use (Apache)

```bash
# Stop Apache
sudo systemctl stop apache2
sudo systemctl disable apache2

# Or use a different port for nosrat-panel
# Edit /etc/nginx/sites-available/nosrat-panel
# Change: listen 80; → listen 8080;
# Access: http://YOUR_IP:8080/
```

---

## 📞 Getting Help

- 📚 [Full Documentation](README.md)
- 🐛 [Report a Bug](https://github.com/pdnczone/nosrat-panel/issues)
- 💬 [Telegram Support](https://t.me/dncdirect)
- 📺 [YouTube Tutorials](https://youtube.com/@PDNC30)
