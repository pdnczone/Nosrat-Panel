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

# ── Constants ─────────────────────────────────────────────────────────────
INSTALL_DIR="/opt/nosrat-panel"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_FILE="/etc/systemd/system/nosrat-panel-backend.service"
NGINX_CONF="/etc/nginx/sites-available/nosrat-panel"
REQUIRED_NODE_MAJOR=20
REQUIRED_NODE_MINOR=19
REQUIRED_NODE_VERSION="${REQUIRED_NODE_MAJOR}.${REQUIRED_NODE_MINOR}.0"

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
# Try to find and load NVM from common locations
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

# ── Node.js Version Check ─────────────────────────────────────────────────
# Returns 0 if Node.js >= REQUIRED_NODE_VERSION is available
check_node_version() {
    if ! command -v node &>/dev/null; then
        return 1
    fi
    local version
    version=$(node -v 2>/dev/null | sed 's/^v//')
    if [[ -z "$version" ]]; then
        return 1
    fi
    local major minor patch
    IFS='.' read -r major minor patch <<< "$version"
    if [[ "$major" -gt "$REQUIRED_NODE_MAJOR" ]] || \
       [[ "$major" -eq "$REQUIRED_NODE_MAJOR" && "$minor" -ge "$REQUIRED_NODE_MINOR" ]]; then
        log "Node.js v$version detected (>= v$REQUIRED_NODE_VERSION required) ✓"
        return 0
    fi
    warn "Node.js v$version detected — need v$REQUIRED_NODE_VERSION+"
    return 1
}

# ── Install Node.js via NodeSource (apt) ──────────────────────────────────
install_node_apt() {
    log "Installing Node.js v20 from NodeSource repository..."
    apt-get update -qq
    if curl -fsSL https://deb.nodesource.com/setup_20.x | bash - 2>&1 | tail -3; then
        apt-get update -qq
        apt-get install -y --no-install-recommends nodejs
        log "Node.js $(node -v) installed via apt"
        return 0
    else
        warn "NodeSource setup failed"
        return 1
    fi
}

# ── Install Node.js via NVM ───────────────────────────────────────────────
install_node_nvm() {
    log "Installing Node.js v20 via NVM..."
    # Install NVM if not present
    if [[ ! -d "/root/.nvm" ]] && [[ ! -d "$HOME/.nvm" ]]; then
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash - 2>&1 | tail -3
    fi
    load_nvm || { warn "NVM load failed"; return 1; }
    
    nvm install 20
    nvm alias default 20
    nvm use 20
    
    # Symlink to /usr/local/bin for system-wide access
    local node_bin
    node_bin=$(nvm which 20 2>/dev/null | head -1)
    if [[ -n "$node_bin" ]]; then
        ln -sf "$node_bin" /usr/local/bin/node
        ln -sf "$(dirname "$node_bin")/npm" /usr/local/bin/npm
        ln -sf "$(dirname "$node_bin")/npx" /usr/local/bin/npx
    fi
    log "Node.js $(node -v) installed via NVM"
    return 0
}

# ── Install Node.js standalone binary (last resort) ───────────────────────
install_node_standalone() {
    log "Downloading standalone Node.js v${REQUIRED_NODE_VERSION} binary..."
    local arch node_arch
    arch=$(uname -m)
    case "$arch" in
        x86_64)  node_arch="x64" ;;
        aarch64) node_arch="arm64" ;;
        armv7l)  node_arch="armv7l" ;;
        *) die "Unsupported architecture: $arch" ;;
    esac
    local node_url="https://nodejs.org/dist/v${REQUIRED_NODE_VERSION}/node-v${REQUIRED_NODE_VERSION}-linux-${node_arch}.tar.xz"
    curl -fsSL "$node_url" | tar -xJ -C /usr/local --strip-components=1
    log "Node.js $(node -v) installed standalone to /usr/local"
    return 0
}

# ── Ensure Node.js >= 20.19.0 ─────────────────────────────────────────────
ensure_node() {
    # First, try to load NVM if available
    load_nvm
    
    # Check if we already have a valid Node.js
    if check_node_version; then
        # Verify npm is also available
        if command -v npm &>/dev/null; then
            log "Using existing Node.js $(node -v) with npm $(npm -v)"
            return 0
        else
            warn "Node.js found but npm missing"
        fi
    fi
    
    # No valid Node.js found - need to install
    warn "No suitable Node.js found. Installing Node.js v20..."
    
    # Try apt (NodeSource) first on Debian/Ubuntu
    if [[ "$PKG_MGR" == "apt" ]]; then
        if install_node_apt; then
            return 0
        fi
        warn "apt install failed, trying NVM..."
    fi
    
    # Try NVM
    if install_node_nvm; then
        return 0
    fi
    
    # Last resort: standalone binary
    if install_node_standalone; then
        return 0
    fi
    
    die "All Node.js installation methods failed"
}

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

# ── Step 2: Install system dependencies ──────────────────────────────────
header "Step 2/7: Installing system dependencies"
export DEBIAN_FRONTEND=noninteractive

if [[ "$PKG_MGR" == "apt" ]]; then
    apt-get update -qq
    
    # First, ensure we have Node.js >= 20.19.0
    # This will use existing NVM Node.js if valid, otherwise install
    ensure_node
    
    # Repair any broken package state
    log "Repairing package state..."
    apt-mark unhold nodejs npm 2>/dev/null || true
    dpkg --configure -a 2>/dev/null || true
    apt-get -f install -y 2>/dev/null || true
    apt-get update -qq
    
    # Install system dependencies
    # NOTE: nodejs and npm are intentionally omitted if we already have valid Node.js
    log "Installing system dependencies (python3, nginx, certbot, git, etc.)..."
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        nginx certbot python3-certbot-nginx \
        git curl jq openssl 2>&1 | tail -5
    
    # Verify Node.js is still working
    if ! check_node_version; then
        warn "Node.js verification failed after apt install"
        ensure_node
    fi
    
elif [[ "$PKG_MGR" == "dnf" || "$PKG_MGR" == "yum" ]]; then
    # On RHEL-based, install nodejs/npm via package manager
    ensure_node
    $PKG_MGR install -y python3 python3-pip \
        nginx certbot python3-certbot-nginx \
        git curl jq openssl 2>&1 | tail -5
fi

log "Dependencies installed (Node.js $(node -v 2>/dev/null || echo 'N/A'), npm $(npm -v 2>/dev/null || echo 'N/A'))"

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

# Ensure NVM is loaded for npm
load_nvm

# Verify Node.js and npm are available
log "Verifying Node.js and npm..."
node -v
npm -v
command -v node
command -v npm

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