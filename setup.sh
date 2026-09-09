#!/usr/bin/env bash
# nosrat-panel installer — Smite-powered backend, Nosrat WebUI
# Usage: sudo bash setup.sh
set -Eeo pipefail

# ── Colors ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

# ── Helpers ────────────────────────────────────────────────────────────────
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
die()  { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }
header() {
    echo ""
    echo -e "${CYAN}━━━ $* ━━━${NC}"
    echo ""
}

# ── Constants ─────────────────────────────────────────────────────────────
INSTALL_DIR="/opt/nosrat-panel"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_FILE="/etc/systemd/system/nosrat-panel-backend.service"
NGINX_CONF="/etc/nginx/sites-available/nosrat-panel"

# Minimum Node.js version required by frontend dependencies
REQUIRED_NODE_MAJOR=22
REQUIRED_NODE_MINOR=12
REQUIRED_NODE_PATCH=0
REQUIRED_NODE_LABEL="${REQUIRED_NODE_MAJOR}.${REQUIRED_NODE_MINOR}.${REQUIRED_NODE_PATCH}"

# ── Root check ────────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Run as root: sudo bash setup.sh"

# ── PDNC Logo Banner ──────────────────────────────────────────────────────
echo -e "${CYAN}"
cat << 'EOF'
 ____  ____  _   _  ____ 
|  _ \|  _ \| \ | |/ ___|
| |_) | | | |  \| | |    
|  __/| |_| | |\  | |___ 
|_|   |____/|_| \_|\____|
                         
EOF
echo -e "${BOLD}NOSRAT WebUI Panel Installer${NC}"
echo -e "${YELLOW}Secure, DPI-Resistant Multi-Server Tunnel Management${NC}"
echo ""

# ── NVM Detection & Setup ─────────────────────────────────────────────────
load_nvm() {
    local nvm_dirs=("/root/.nvm" "$HOME/.nvm" "/usr/local/nvm" "/opt/nvm")
    for dir in "${nvm_dirs[@]}"; do
        if [[ -s "$dir/nvm.sh" ]]; then
            export NVM_DIR="$dir"
            # shellcheck disable=SC1090
            . "$NVM_DIR/nvm.sh"
            log "NVM loaded from $NVM_DIR"
            return 0
        fi
    done
    return 1
}

# ── Node.js Version Check (numeric) ───────────────────────────────────────
node_version_satisfies() {
    local current="$1"
    local major minor patch
    IFS='.' read -r major minor patch <<< "$current"
    [[ -z "$major" || -z "$minor" ]] && return 1
    patch="${patch:-0}"

    if [[ "$major" -gt "$REQUIRED_NODE_MAJOR" ]]; then
        return 0
    elif [[ "$major" -eq "$REQUIRED_NODE_MAJOR" ]]; then
        if [[ "$minor" -gt "$REQUIRED_NODE_MINOR" ]]; then
            return 0
        elif [[ "$minor" -eq "$REQUIRED_NODE_MINOR" ]]; then
            [[ "$patch" -ge "$REQUIRED_NODE_PATCH" ]] && return 0
        fi
    fi
    return 1
}

check_node_version() {
    if ! command -v node &>/dev/null; then
        return 1
    fi
    local version
    version=$(node -v 2>/dev/null | sed 's/^v//')
    if [[ -z "$version" ]]; then
        return 1
    fi
    if node_version_satisfies "$version"; then
        log "Node.js v$version detected (>= v${REQUIRED_NODE_LABEL} required)"
        return 0
    fi
    warn "Node.js v$version detected — project requires v${REQUIRED_NODE_LABEL}+"
    return 1
}

# ── Install Node.js via NVM ───────────────────────────────────────────────
install_node_nvm() {
    log "Installing Node.js v${REQUIRED_NODE_MAJOR} via NVM..."
    if [[ ! -d "/root/.nvm" ]] && [[ ! -d "$HOME/.nvm" ]]; then
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash - 2>&1 | tail -3
    fi
    load_nvm || { warn "NVM load failed"; return 1; }

    nvm install 22
    nvm alias default 22
    nvm use 22

    if ! check_node_version; then
        warn "NVM-installed Node.js $(node -v) still below v${REQUIRED_NODE_LABEL}"
        return 1
    fi

    local node_bin
    node_bin=$(nvm which 22 2>/dev/null | head -1)
    if [[ -n "$node_bin" ]]; then
        ln -sf "$node_bin" /usr/local/bin/node
        ln -sf "$(dirname "$node_bin")/npm" /usr/local/bin/npm
        ln -sf "$(dirname "$node_bin")/npx" /usr/local/bin/npx
    fi
    log "Node.js $(node -v) installed via NVM"
    return 0
}

# ── Ensure Node.js >= 22.12.0 (for frontend build only) ───────────────────
ensure_node() {
    load_nvm
    if check_node_version; then
        if command -v npm &>/dev/null; then
            log "Using existing Node.js $(node -v) with npm $(npm -v)"
            return 0
        else
            warn "Node.js found but npm missing"
        fi
    fi

    warn "No suitable Node.js found. Installing Node.js v${REQUIRED_NODE_MAJOR}..."
    if [[ -d "/root/.nvm" ]] || [[ -d "$HOME/.nvm" ]]; then
        if install_node_nvm; then
            return 0
        fi
    fi
    die "Node.js installation failed. Install Node.js >= v${REQUIRED_NODE_LABEL} manually."
}

# ── Verify Node.js & npm ──────────────────────────────────────────────────
verify_node_npm() {
    echo ""
    echo -e "  ${CYAN}── Node.js & npm verification ──${NC}"
    if ! command -v node &>/dev/null; then die "node command not found"; fi
    if ! command -v npm &>/dev/null; then die "npm command not found"; fi
    node -v
    npm -v
    command -v node
    command -v npm
    if ! check_node_version; then
        die "Node.js $(node -v) does not meet project minimum v${REQUIRED_NODE_LABEL}. npm will NOT run."
    fi
    log "Node.js & npm verified (>= v${REQUIRED_NODE_LABEL})"
    echo ""
}

# ── Install Docker & Docker Compose ───────────────────────────────────────
install_docker() {
    if command -v docker &>/dev/null && docker compose version &>/dev/null; then
        log "Docker & Docker Compose already installed"
        return 0
    fi

    header "Installing Docker & Docker Compose"
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg lsb-release 2>&1 | tail -3

    # Add Docker GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Add Docker repository
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin 2>&1 | tail -5

    log "Docker & Docker Compose installed"
}

# ── Build frontend ────────────────────────────────────────────────────────
build_frontend() {
    header "Building Nosrat WebUI (Svelte 5 + Vite + Tailwind)"
    cd "$INSTALL_DIR/frontend"

    load_nvm
    verify_node_npm

    set +e
    log "Running npm install..."
    npm install --legacy-peer-deps --no-audit --no-fund 2>&1 | tail -10
    INSTALL_EXIT=$?
    if [[ $INSTALL_EXIT -ne 0 ]]; then
        echo -e "${YELLOW}[!]${NC} npm install failed (exit code: $INSTALL_EXIT)"
        echo -e "${YELLOW}[!]${NC} Check error messages above for details"
    fi
    log "Running npm build..."
    npm run build 2>&1 | tail -10
    BUILD_EXIT=$?
    if [[ $BUILD_EXIT -ne 0 ]]; then
        echo -e "${YELLOW}[!]${NC} npm build failed (exit code: $BUILD_EXIT)"
    fi
    log "Frontend built"
    set -e
}

# ── Prepare Smite panel backend ───────────────────────────────────────────
prepare_panel() {
    header "Preparing Smite Panel Backend (FastAPI + Tunnel Engines)"
    cd "$INSTALL_DIR"

    # Create .env for panel
    cat > .env << EOF
PANEL_HOST=0.0.0.0
PANEL_PORT=8000
PANEL_DOMAIN=
HTTPS_ENABLED=false
PANEL_SSL_CERT_PATH=./panel/certs/server.crt
PANEL_SSL_KEY_PATH=./panel/certs/server.key
DOCS_ENABLED=true

DB_TYPE=sqlite
DB_PATH=./panel/data/nosrat.db

NODE_PORT=4443
NODE_CERT_PATH=./panel/certs/ca.crt
NODE_KEY_PATH=./panel/certs/ca.key
NODE_SERVER_CERT_PATH=./panel/certs/ca-server.crt
NODE_SERVER_KEY_PATH=./panel/certs/ca-server.key

SECRET_KEY=$(openssl rand -hex 32)

SMITE_HTTP_PORT=80
SMITE_HTTPS_PORT=443
SMITE_SSL_DOMAIN=REPLACE_DOMAIN

SMITE_VERSION=latest
EOF

    # Create directories
    mkdir -p panel/data panel/certs
    touch panel/certs/ca.crt panel/certs/ca.key panel/certs/ca-server.crt panel/certs/ca-server.key

    log "Panel configuration ready"
}

# ── Install systemd service for panel (Docker compose) ────────────────────
install_panel_service() {
    header "Installing systemd service for Smite Panel"
    cat > "$SERVICE_FILE" << 'EOF'
[Unit]
Description=Nosrat Panel Backend (Smite + FastAPI)
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/nosrat-panel
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable nosrat-panel-backend.service
    log "Systemd service installed and enabled"
}

# ── Install nginx config ──────────────────────────────────────────────────
install_nginx() {
    header "Configuring Nginx"
    cat > "$NGINX_CONF" << 'EOF'
# nosrat-panel nginx configuration
server {
    listen 80;
    listen [::]:80;
    server_name _;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    client_max_body_size 10M;

    # Frontend static files
    root /opt/nosrat-panel/frontend/dist;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    # API reverse proxy to panel backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_http_version 1.1;
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # WebSocket
    location /ws {
        proxy_pass http://127.0.0.1:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host $host;
    }
    location /openapi.json {
        proxy_pass http://127.0.0.1:8000/openapi.json;
        proxy_set_header Host $host;
    }

    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
}
EOF

    ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/nosrat-panel
    rm -f /etc/nginx/sites-enabled/default
    if nginx -t 2>/dev/null; then
        systemctl reload nginx 2>/dev/null || true
        log "Nginx configured and reloaded"
    else
        warn "Nginx config has issues - please check manually"
    fi
}

# ── Apply network optimizations ───────────────────────────────────────────
apply_network_optimizations() {
    log "Applying network optimizations..."
    if [[ -f "/etc/sysctl.conf" ]]; then
        if [[ ! -f "/etc/sysctl.conf.nosrat-backup" ]]; then
            cp /etc/sysctl.conf /etc/sysctl.conf.nosrat-backup
        fi
        if ! grep -q "# Nosrat Network Optimizations" /etc/sysctl.conf; then
            cat >> /etc/sysctl.conf << 'EOF'

# Nosrat Network Optimizations
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.ip_local_port_range = 10000 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 30
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_intvl = 60
net.ipv4.tcp_keepalive_probes = 3
net.ipv4.tcp_slow_start_after_idle = 0
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.ipv4.udp_mem = 3145728 4194304 16777216
net.ipv4.ip_forward = 1
EOF
            sysctl -p > /dev/null 2>&1 || true
            log "Network optimizations applied"
        else
            log "Network optimizations already applied"
        fi
    fi

    # File descriptor limits
    if [[ -f "/etc/security/limits.conf" ]]; then
        if ! grep -q "# Nosrat File Descriptor Limits" /etc/security/limits.conf; then
            cat >> /etc/security/limits.conf << 'EOF'

# Nosrat File Descriptor Limits
* soft nofile 65535
* hard nofile 65535
root soft nofile 65535
root hard nofile 65535
EOF
            log "File descriptor limits increased"
        fi
        ulimit -n 65535 2>/dev/null || true
    fi

    # BBR
    if modprobe -n tcp_bbr 2>/dev/null; then
        if ! grep -q "tcp_bbr" /etc/modules-load.d/*.conf 2>/dev/null && ! grep -q "tcp_bbr" /etc/modules 2>/dev/null; then
            echo "tcp_bbr" | tee -a /etc/modules-load.d/nosrat.conf > /dev/null 2>&1 || echo "tcp_bbr" >> /etc/modules 2>/dev/null || true
            modprobe tcp_bbr 2>/dev/null || true
            sysctl -w net.ipv4.tcp_congestion_control=bbr > /dev/null 2>&1 || true
            sysctl -w net.core.default_qdisc=fq > /dev/null 2>&1 || true
            log "BBR congestion control enabled"
        fi
    fi
}

# ── Install CLI tools ─────────────────────────────────────────────────────
install_cli() {
    log "Installing CLI tools..."
    if [[ -f "cli/install_cli.sh" ]]; then
        bash cli/install_cli.sh > /dev/null 2>&1 || true
    else
        if [[ -f "cli/smite.py" ]]; then
            cp cli/smite.py /usr/local/bin/nosrat 2>/dev/null || true
            chmod +x /usr/local/bin/nosrat 2>/dev/null || true
        fi
        if [[ -f "cli/smite-node.py" ]]; then
            cp cli/smite-node.py /usr/local/bin/nosrat-node 2>/dev/null || true
            chmod +x /usr/local/bin/nosrat-node 2>/dev/null || true
        fi
    fi
    log "CLI tools installed"
}

# ── Step 1: Detect system ─────────────────────────────────────────────────
header "Step 1/7: Detecting system"
if command -v apt-get &>/dev/null; then
    PKG_MGR="apt"
    log "Detected: Debian/Ubuntu"
else
    die "Unsupported OS. This installer supports Debian/Ubuntu only."
fi

# ── Step 2: Install system dependencies ──────────────────────────────────
header "Step 2/7: Installing system dependencies"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    nginx certbot python3-certbot-nginx \
    git curl jq openssl 2>&1 | tail -5

# Ensure Node.js for frontend build
ensure_node

# Install Docker
install_docker

# ── Step 3: Copy application files ────────────────────────────────────────
header "Step 3/7: Installing nosrat-panel"

if [[ -n "${BASH_SOURCE[0]:-}" ]] && [[ "${BASH_SOURCE[0]}" != "bash" ]] && [[ "${BASH_SOURCE[0]}" != "/dev/stdin" ]] && [[ -f "${BASH_SOURCE[0]}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    log "Installing from local source: $SCRIPT_DIR"
else
    log "Cloning from GitHub..."
    SCRIPT_DIR="/tmp/nosrat-panel-install"
    rm -rf "$SCRIPT_DIR"
    if ! git clone --depth 1 https://github.com/pdnczone/Nosrat-Panel.git "$SCRIPT_DIR" 2>&1 | tail -3; then
        die "Failed to clone repository from GitHub"
    fi
fi

mkdir -p "$INSTALL_DIR"

# Copy backend (panel, node), frontend, systemd, docs
for dir in panel node frontend systemd docs; do
    if [[ -d "$SCRIPT_DIR/$dir" ]]; then
        cp -r "$SCRIPT_DIR/$dir" "$INSTALL_DIR/"
        log "Copied $dir/"
    else
        warn "$dir/ not found in source - skipping"
    fi
done

# Also copy scripts, cli, docker-compose, nginx templates, Makefile
for file in scripts cli docker-compose.yml nginx Makefile; do
    if [[ -e "$SCRIPT_DIR/$file" ]]; then
        cp -r "$SCRIPT_DIR/$file" "$INSTALL_DIR/"
        log "Copied $file"
    fi
done

log "Application files copied to $INSTALL_DIR"

# ── Step 4: Prepare panel backend ─────────────────────────────────────────
header "Step 4/7: Preparing Smite Panel Backend"
prepare_panel

# ── Step 5: Build frontend ────────────────────────────────────────────────
header "Step 5/7: Building Frontend"
build_frontend

# ── Step 6: Install systemd + nginx ───────────────────────────────────────
header "Step 6/7: Installing systemd service + Nginx"
install_panel_service
install_nginx

# ── Step 7: Apply network optimizations + start ───────────────────────────
header "Step 7/7: Applying optimizations & starting services"
apply_network_optimizations
install_cli

mkdir -p /var/log/nosrat-panel /etc/nosrat /etc/swanctl/conf.d /etc/nosrat/secrets /etc/strongswan /etc/wireguard /etc/ghosttunnel /etc/ghost_tunnel /etc/nginx /var/lib/strongswan /run/strongswan /var/www/html/current

# Start panel
systemctl restart nosrat-panel-backend.service 2>/dev/null
sleep 5

if systemctl is-active --quiet nosrat-panel-backend.service 2>/dev/null; then
    log "Nosrat Panel Backend (Smite) is running"
else
    warn "Backend may have issues - check: journalctl -u nosrat-panel-backend -n 30"
    docker compose logs --tail=50 2>/dev/null || true
fi

# ── Final info ────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ✅  nosrat-panel installed!                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Access the panel:${NC}"
echo -e "    ${CYAN}http://$(hostname -I | awk '{print $1}')/${NC}"
echo ""
echo -e "  ${BOLD}Default credentials:${NC}"
echo -e "    Username: ${CYAN}admin${NC}"
echo -e "    Password: ${CYAN}admin${NC}  ${YELLOW}(change immediately!)${NC}"
echo ""
echo -e "  ${BOLD}Service management:${NC}"
echo -e "    ${CYAN}systemctl status nosrat-panel-backend${NC}"
echo -e "    ${CYAN}systemctl restart nosrat-panel-backend${NC}"
echo -e "    ${CYAN}journalctl -u nosrat-panel-backend -f${NC}"
echo -e "    ${CYAN}docker compose logs -f${NC}"
echo ""
echo -e "  ${BOLD}CLI tools:${NC}"
echo -e "    ${CYAN}nosrat status${NC}         # Panel status"
echo -e "    ${CYAN}nosrat admin create${NC}   # Create admin user"
echo -e "    ${CYAN}nosrat-node status${NC}    # Node status"
echo ""
echo -e "  ${BOLD}Enable HTTPS (recommended):${NC}"
echo -e "    ${CYAN}certbot --nginx -d yourdomain.com${NC}"
echo ""
echo -e "  ${YELLOW}📺 YouTube:${NC}    https://youtube.com/@PDNC30"
echo -e "  ${YELLOW}📢 Telegram:${NC}   https://t.me/PDNCzone"
echo ""