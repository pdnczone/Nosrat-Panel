#!/usr/bin/env bash
# nosrat-panel installer
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

# Install Node.js v20 via NVM (fallback when NodeSource fails)
install_node_via_nvm() {
    log "Installing Node.js v20 via NVM..."
    # Install NVM if not present
    if [[ ! -d "/root/.nvm" ]] && [[ ! -d "$HOME/.nvm" ]]; then
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash - 2>&1 | tail -3
    fi
    # Source NVM (try both common locations)
    export NVM_DIR=""
    if [[ -s "/root/.nvm/nvm.sh" ]]; then
        NVM_DIR="/root/.nvm"
    elif [[ -s "$HOME/.nvm/nvm.sh" ]]; then
        NVM_DIR="$HOME/.nvm"
    fi
    if [[ -z "$NVM_DIR" ]]; then
        warn "NVM install failed — trying standalone Node.js binary"
        install_node_standalone
        return
    fi
    \. "$NVM_DIR/nvm.sh"
    # Install and use Node 20
    nvm install 20
    nvm alias default 20
    # Symlink to /usr/local/bin for system-wide access
    NODE_BIN=$(nvm which 20 2>/dev/null | head -1)
    if [[ -n "$NODE_BIN" ]]; then
        ln -sf "$NODE_BIN" /usr/local/bin/node
        ln -sf "$(dirname "$NODE_BIN")/npm" /usr/local/bin/npm
        ln -sf "$(dirname "$NODE_BIN")/npx" /usr/local/bin/npx
    fi
    log "Node.js $(node -v) installed via NVM"
}

# Last resort: download standalone Node.js binary
install_node_standalone() {
    log "Downloading standalone Node.js v20 binary..."
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  NODE_ARCH="x64" ;;
        aarch64) NODE_ARCH="arm64" ;;
        armv7l)  NODE_ARCH="armv7l" ;;
        *) die "Unsupported architecture: $ARCH" ;;
    esac
    NODE_URL="https://nodejs.org/dist/v20.19.0/node-v20.19.0-linux-${NODE_ARCH}.tar.xz"
    curl -fsSL "$NODE_URL" | tar -xJ -C /usr/local --strip-components=1
    log "Node.js $(node -v) installed standalone to /usr/local"
}

# ── Constants ─────────────────────────────────────────────────────────────
INSTALL_DIR="/opt/nosrat-panel"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_FILE="/etc/systemd/system/nosrat-panel-backend.service"
NGINX_CONF="/etc/nginx/sites-available/nosrat-panel"

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

# ── Step 1: Detect package manager ────────────────────────────────────────
header "Step 1/7: Detecting system"
if command -v apt-get &>/dev/null; then
    PKG_MGR="apt"
    log "Detected: Debian/Ubuntu"
elif command -v dnf &>/dev/null; then
    PKG_MGR="dnf"
    log "Detected: RHEL/CentOS/Fedora"
elif command -v yum &>/dev/null; then
    PKG_MGR="yum"
    log "Detected: RHEL/CentOS (yum)"
else
    die "No supported package manager found (apt/dnf/yum)"
fi

# ── Step 2: Install dependencies ──────────────────────────────────────────
header "Step 2/7: Installing system dependencies"
export DEBIAN_FRONTEND=noninteractive

# Check Node.js version early
NODE_VER=0
if command -v node &>/dev/null; then
    NODE_VER=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
    if [[ "$NODE_VER" -lt 20 ]]; then
        warn "Current Node.js v$(node -v | cut -d'v' -f2) detected — frontend requires v20+"
    fi
fi

if [[ "$PKG_MGR" == "apt" ]]; then
    apt-get update -qq

    # ── Remove old Node.js to prevent held/broken package conflicts ──
    if [[ "$NODE_VER" -lt 20 ]] && [[ "$NODE_VER" -gt 0 ]]; then
        log "Removing old Node.js $NODE_VER to avoid package conflicts..."
        # Unhold if held
        apt-mark unhold nodejs 2>/dev/null || true
        # Remove old node and npm
        apt-get remove -y --purge nodejs npm node-* 2>/dev/null || true
        apt-get autoremove -y 2>/dev/null || true
        # Fix any broken state left behind
        dpkg --configure -a 2>/dev/null || true
        apt-get -f install -y 2>/dev/null || true
        # Clean up any stale NodeSource sources
        rm -f /etc/apt/sources.list.d/nodesource.list 2>/dev/null || true
        rm -f /etc/apt/sources.list.d/nodesource.list.gpg 2>/dev/null || true
        apt-get update -qq
        NODE_VER=0
    fi

    # ── Install Node.js v20 from NodeSource ──
    if [[ "$NODE_VER" -lt 20 ]]; then
        log "Adding NodeSource repository for Node.js v20..."
        if curl -fsSL https://deb.nodesource.com/setup_20.x | bash - 2>&1 | tail -3; then
            log "NodeSource repo added successfully"
        else
            warn "NodeSource setup failed — trying NVM fallback"
            install_node_via_nvm
        fi
    fi

    # ── Aggressively fix any broken/held packages BEFORE final install ──
    log "Repairing package state..."
    apt-mark unhold nodejs npm 2>/dev/null || true
    dpkg --configure -a 2>/dev/null || true
    apt-get -f install -y 2>/dev/null || true
    apt-get install -f -y 2>/dev/null || true
    apt-get update -qq

    # ── Install all system dependencies ──
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv nodejs npm \
        nginx certbot python3-certbot-nginx \
        git curl jq openssl 2>&1 | tail -5

    # Verify Node.js version
    if command -v node &>/dev/null; then
        FINAL_NODE=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
        if [[ "$FINAL_NODE" -lt 20 ]]; then
            warn "Node.js still v$(node -v | cut -d'v' -f2) — falling back to NVM"
            install_node_via_nvm
        fi
    fi

elif [[ "$PKG_MGR" == "dnf" || "$PKG_MGR" == "yum" ]]; then
    $PKG_MGR install -y python3 python3-pip nodejs npm \
        nginx certbot python3-certbot-nginx \
        git curl jq openssl 2>&1 | tail -5
fi
log "Dependencies installed (Node.js $(node -v 2>/dev/null || echo 'N/A'))"

# ── Step 3: Copy application files ────────────────────────────────────────
header "Step 3/7: Installing nosrat-panel"

# When invoked via `curl | bash`, BASH_SOURCE is not set, so we clone
# the repo from GitHub instead of trying to use the script's directory.
# When invoked locally (`sudo ./setup.sh`), we use the script's directory.
if [[ -n "${BASH_SOURCE[0]:-}" ]] && [[ "${BASH_SOURCE[0]}" != "bash" ]] && [[ "${BASH_SOURCE[0]}" != "/dev/stdin" ]] && [[ -f "${BASH_SOURCE[0]}" ]]; then
    # Local execution
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    log "Installing from local source: $SCRIPT_DIR"
else
    # Piped execution (curl | bash) - clone from GitHub
    log "Cloning from GitHub..."
    SCRIPT_DIR="/tmp/nosrat-panel-install"
    rm -rf "$SCRIPT_DIR"
    if ! git clone --depth 1 https://github.com/pdnczone/Nosrat-Panel.git "$SCRIPT_DIR" 2>&1 | tail -3; then
        die "Failed to clone repository from GitHub"
    fi
fi

mkdir -p "$INSTALL_DIR"

# Copy backend, frontend, node-agent, systemd, docs
for dir in backend frontend node-agent systemd docs; do
    if [[ -d "$SCRIPT_DIR/$dir" ]]; then
        cp -r "$SCRIPT_DIR/$dir" "$INSTALL_DIR/"
        log "Copied $dir/"
    else
        warn "$dir/ not found in source - skipping"
    fi
done

log "Application files copied to $INSTALL_DIR"

# ── Step 4: Python venv + dependencies ────────────────────────────────────
header "Step 4/7: Setting up Python environment"
python3 -m venv "$VENV_DIR"
log "Virtual environment created at $VENV_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
pip install -r "$INSTALL_DIR/backend/requirements.txt" --quiet 2>&1 | tail -5
log "Python dependencies installed"

# ── Step 5: Build frontend ────────────────────────────────────────────────
header "Step 5/7: Building frontend"
cd "$INSTALL_DIR/frontend"
# Disable set -e for this section so individual failures don't abort install
set +e
log "Running npm install (this may take a few minutes)..."
# Use --legacy-peer-deps to work around svelte-chartjs/Svelte 5 peer dep mismatch
npm install --legacy-peer-deps --no-audit --no-fund 2>&1 | tail -10
INSTALL_EXIT=$?
if [[ $INSTALL_EXIT -ne 0 ]]; then
    echo -e "${YELLOW}[!]${NC} npm install failed (exit code: $INSTALL_EXIT)"
    if command -v node &>/dev/null; then
        CURRENT_NODE=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
        if [[ "$CURRENT_NODE" -lt 20 ]]; then
            echo -e "${YELLOW}[!]${NC} CAUSE: Node.js v$CURRENT_NODE detected — frontend requires Node.js v20+"
            echo -e "${YELLOW}[!]${NC} FIX: Run this to upgrade:"
            echo -e "${CYAN}    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -${NC}"
            echo -e "${CYAN}    apt-get install -y nodejs${NC}"
            echo -e "${YELLOW}[!]${NC} Then re-run: cd $INSTALL_DIR/frontend && npm install && npm run build"
        else
            echo -e "${YELLOW}[!]${NC} Check error messages above for details"
        fi
    else
        echo -e "${YELLOW}[!]${NC} Node.js not found. Install v20+ and re-run build."
    fi
    echo -e "${YELLOW}[!]${NC} Continuing anyway - frontend may need manual build later"
fi
log "Running npm build..."
npm run build 2>&1 | tail -10
BUILD_EXIT=$?
if [[ $BUILD_EXIT -ne 0 ]]; then
    echo -e "${YELLOW}[!]${NC} npm build failed (exit code: $BUILD_EXIT) - check error messages above"
    echo -e "${YELLOW}[!]${NC} Continuing anyway - you can rebuild manually later"
fi
log "Frontend built"
set -e

# ── Step 6: Install systemd service ───────────────────────────────────────
header "Step 6/7: Installing systemd service"
# Disable set -e for this section so individual failures don't abort install
set +e
if [[ -f "$INSTALL_DIR/systemd/nosrat-panel-backend.service" ]]; then
    cp "$INSTALL_DIR/systemd/nosrat-panel-backend.service" "$SERVICE_FILE"
    systemctl daemon-reload
    systemctl enable nosrat-panel-backend.service
    log "Systemd service installed and enabled"
else
    warn "systemd service file not found - skipping"
fi

# Install nginx config
if [[ -f "$INSTALL_DIR/systemd/nginx-nosrat-panel.conf" ]]; then
    cp "$INSTALL_DIR/systemd/nginx-nosrat-panel.conf" "$NGINX_CONF"
    ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/nosrat-panel
    # Remove default site if present
    rm -f /etc/nginx/sites-enabled/default
    if nginx -t 2>/dev/null; then
        systemctl reload nginx 2>/dev/null || true
        log "Nginx configured and reloaded"
    else
        warn "Nginx config has issues - please check manually"
    fi
fi
set -e

# ── Step 7: Initialize database and start ─────────────────────────────────
header "Step 7/7: Initializing and starting"
mkdir -p /var/log/nosrat-panel /etc/nosrat /etc/swanctl/conf.d /etc/nosrat/secrets /etc/strongswan /etc/wireguard /etc/ghosttunnel /etc/ghost_tunnel /etc/nginx /var/lib/strongswan /run/strongswan /var/www/html/current
set +e

# Start the service
if [[ -f "$SERVICE_FILE" ]]; then
    systemctl restart nosrat-panel-backend.service 2>/dev/null
    sleep 3

    if systemctl is-active --quiet nosrat-panel-backend.service 2>/dev/null; then
        log "nosrat-panel backend is running"
    else
        warn "Backend failed to start - check: journalctl -u nosrat-panel-backend -n 20"
    fi
fi
set -e

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
echo ""
echo -e "  ${BOLD}Enable HTTPS (recommended):${NC}"
echo -e "    ${CYAN}certbot --nginx -d yourdomain.com${NC}"
echo ""
echo -e "  ${YELLOW}📺 YouTube:${NC}    https://youtube.com/@PDNC30"
echo -e "  ${YELLOW}📢 Telegram:${NC}   https://t.me/PDNCzone"
echo ""
