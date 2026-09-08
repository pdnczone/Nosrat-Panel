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

# Minimum Node.js version required by frontend dependencies
# puppeteer@25.10.0 requires node >=22.12.0
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

# ── Node.js Version Check (numeric, not just major) ───────────────────────
# Compares Node.js version against required minimum using numeric comparison.
# Returns 0 if current Node.js >= REQUIRED_NODE_MAJOR.MINOR.PATCH
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

# Returns 0 if a usable Node.js (>= required) is available
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

# ── Install Node.js via apt/NodeSource ────────────────────────────────────
install_node_apt() {
    log "Installing Node.js v${REQUIRED_NODE_MAJOR} from NodeSource repository..."
    apt-get update -qq
    if curl -fsSL "https://deb.nodesource.com/setup_${REQUIRED_NODE_MAJOR}.x" | bash - 2>&1 | tail -3; then
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
    log "Installing Node.js v${REQUIRED_NODE_MAJOR} via NVM..."
    # Install NVM if not present
    if [[ ! -d "/root/.nvm" ]] && [[ ! -d "$HOME/.nvm" ]]; then
        curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash - 2>&1 | tail -3
    fi
    load_nvm || { warn "NVM load failed"; return 1; }

    # Install the "22" LTS line; nvm installs latest 22.x
    nvm install 22
    nvm alias default 22
    nvm use 22

    # Verify the installed version actually satisfies the requirement
    if ! check_node_version; then
        warn "NVM-installed Node.js $(node -v) still below v${REQUIRED_NODE_LABEL}"
        return 1
    fi

    # Symlink for system-wide access
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

# ── Install Node.js standalone binary (last resort) ───────────────────────
install_node_standalone() {
    # Use a known-good 22.x release >= 22.12.0
    local node_release="22.12.0"
    log "Downloading standalone Node.js v${node_release} binary..."
    local arch node_arch
    arch=$(uname -m)
    case "$arch" in
        x86_64)  node_arch="x64" ;;
        aarch64) node_arch="arm64" ;;
        armv7l)  node_arch="armv7l" ;;
        *) die "Unsupported architecture: $arch" ;;
    esac
    local node_url="https://nodejs.org/dist/v${node_release}/node-v${node_release}-linux-${node_arch}.tar.xz"
    curl -fsSL "$node_url" | tar -xJ -C /usr/local --strip-components=1
    if check_node_version; then
        log "Node.js $(node -v) installed standalone to /usr/local"
        return 0
    fi
    warn "Standalone install failed"
    return 1
}

# ── Ensure Node.js >= 22.12.0 ─────────────────────────────────────────────
ensure_node() {
    # First, try to load NVM if available (so an NVM-managed node is found)
    load_nvm

    # If we already have a valid Node.js, use it.
    if check_node_version; then
        if command -v npm &>/dev/null; then
            log "Using existing Node.js $(node -v) with npm $(npm -v)"
            return 0
        else
            warn "Node.js found but npm missing"
        fi
    fi

    # Node.js is missing OR below 22.12.0 — need to upgrade/install.
    warn "No suitable Node.js found. Installing Node.js v${REQUIRED_NODE_MAJOR} (>= v${REQUIRED_NODE_LABEL})..."

    # 1) If NVM exists, prefer upgrading via NVM (keeps NVM management intact)
    if [[ -d "/root/.nvm" ]] || [[ -d "$HOME/.nvm" ]]; then
        if install_node_nvm; then
            return 0
        fi
        warn "NVM upgrade failed, trying apt fallback..."
    fi

    # 2) Try apt (NodeSource) on Debian/Ubuntu
    if [[ "$PKG_MGR" == "apt" ]]; then
        if install_node_apt; then
            return 0
        fi
        warn "apt install failed, trying NVM..."
    fi

    # 3) NVM (if not already tried)
    if install_node_nvm; then
        return 0
    fi

    # 4) Last resort: standalone binary
    if install_node_standalone; then
        return 0
    fi

    die "All Node.js installation methods failed (need >= v${REQUIRED_NODE_LABEL})"
}

# ── Verify Node.js & npm (numeric check) ──────────────────────────────────
verify_node_npm() {
    echo ""
    echo -e "  ${CYAN}── Node.js & npm verification ──${NC}"
    if ! command -v node &>/dev/null; then
        die "node command not found"
    fi
    if ! command -v npm &>/dev/null; then
        die "npm command not found"
    fi

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

    # Ensure we have Node.js >= 22.12.0 (preserves NVM-installed node if valid)
    ensure_node

    # Repair any broken package state
    log "Repairing package state..."
    apt-mark unhold nodejs npm 2>/dev/null || true
    dpkg --configure -a 2>/dev/null || true
    apt-get -f install -y 2>/dev/null || true
    apt-get update -qq

    # Install system dependencies.
    # NOTE: nodejs and npm are intentionally NOT listed here so that an
    # NVM-managed Node/npm is never overwritten by the apt versions.
    log "Installing system dependencies (python3, nginx, certbot, git, etc.)..."
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        nginx certbot python3-certbot-nginx \
        git curl jq openssl 2>&1 | tail -5

    # Verify Node.js is still working and >= required
    if ! check_node_version; then
        warn "Node.js verification failed after apt install"
        ensure_node
    fi

elif [[ "$PKG_MGR" == "dnf" || "$PKG_MGR" == "yum" ]]; then
    # On RHEL-based, ensure Node.js then install system deps
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

# Ensure NVM is loaded (in case shell environment didn't have it)
load_nvm

# Final verification: Node.js >= 22.12.0 AND npm present.
# If Node is too old, abort BEFORE running npm.
verify_node_npm

# Disable set -e for this section so individual failures don't abort install
set +e
log "Running npm install (this may take a few minutes)..."
# Use --legacy-peer-deps to work around svelte-chartjs/Svelte 5 peer dep mismatch
npm install --legacy-peer-deps --no-audit --no-fund 2>&1 | tail -10
INSTALL_EXIT=$?
if [[ $INSTALL_EXIT -ne 0 ]]; then
    echo -e "${YELLOW}[!]${NC} npm install failed (exit code: $INSTALL_EXIT)"
    if command -v node &>/dev/null; then
        CURRENT_NODE=$(node -v | sed 's/^v//')
        if ! node_version_satisfies "$CURRENT_NODE"; then
            echo -e "${YELLOW}[!]${NC} CAUSE: Node.js v$CURRENT_NODE detected — frontend requires Node.js v${REQUIRED_NODE_LABEL}+"
            echo -e "${YELLOW}[!]${NC} FIX: Install or upgrade Node.js:"
            echo -e "${CYAN}    export NVM_DIR=\"/root/.nvm\" && [ -s \"\$NVM_DIR/nvm.sh\" ] && . \"\$NVM_DIR/nvm.sh\"${NC}"
            echo -e "${CYAN}    nvm install 22 && nvm use 22 && nvm alias default 22${NC}"
            echo -e "${YELLOW}[!]${NC} Then re-run: cd $INSTALL_DIR/frontend && npm install && npm run build"
        else
            echo -e "${YELLOW}[!]${NC} Check error messages above for details"
        fi
    else
        echo -e "${YELLOW}[!]${NC} Node.js not found. Install v${REQUIRED_NODE_LABEL}+ and re-run build."
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