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

# ── Root check ────────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Run as root: sudo bash setup.sh"

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
if [[ "$PKG_MGR" == "apt" ]]; then
    apt-get update -qq
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv nodejs npm \
        nginx certbot python3-certbot-nginx \
        git curl jq openssl 2>&1 | tail -5
elif [[ "$PKG_MGR" == "dnf" || "$PKG_MGR" == "yum" ]]; then
    $PKG_MGR install -y python3 python3-pip nodejs npm \
        nginx certbot python3-certbot-nginx \
        git curl jq openssl 2>&1 | tail -5
fi
log "Dependencies installed"

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
    echo -e "${YELLOW}[!]${NC} npm install failed - check Node.js version (need 18+)"
    echo -e "${YELLOW}[!]${NC} Continuing anyway - frontend may need manual build later"
fi
log "Running npm build..."
npm run build 2>&1 | tail -10
BUILD_EXIT=$?
if [[ $BUILD_EXIT -ne 0 ]]; then
    echo -e "${YELLOW}[!]${NC} npm build failed - check error messages above"
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
mkdir -p /var/log/nosrat-panel
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
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ✅  nosrat-panel installed!                    ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
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
echo -e "  ${YELLOW}💬 Support:${NC}    https://t.me/dncdirect"
echo ""
