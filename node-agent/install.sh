#!/usr/bin/env bash
# nosrat-node install.sh — invoked by curl|bash from the panel.
#
# Idempotent: re-running it re-creates the venv and updates files in place.
# Safe to run with ``--force`` to start from a clean slate.
#
# Usage:
#   curl -sL https://raw.githubusercontent.com/pdnczone/Nosrat-Panel/main/node-agent/install.sh | \
#       sudo bash -s -- --panel-url=https://panel.example.com \
#                       --token=... --name=iran-1 --location=iran [--force]
#
# All options may also be supplied via environment variables (see below).

set -Eeuo pipefail

# ── Argument parsing ──────────────────────────────────────────────────────

PANEL_URL="${PANEL_URL:-}"
NODE_TOKEN="${NODE_TOKEN:-}"
NODE_NAME="${NODE_NAME:-}"
NODE_LOCATION="${NODE_LOCATION:-}"
AGENT_REPO="${AGENT_REPO:-https://raw.githubusercontent.com/pdnczone/Nosrat-Panel/main}"
FORCE="${FORCE:-0}"
PYTHON_BIN="${PYTHON_BIN:-}"

print()  { printf '\033[1;36m[nodetool]\033[0m %s\n' "$*"; }
warn()   { printf '\033[1;33m[warn]\033[0m %s\n' "$*" >&2; }
fail()   { printf '\033[1;31m[fatal]\033[0m %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --panel-url=*) PANEL_URL="${1#*=}" ;;
        --panel-url)   PANEL_URL="$2"; shift ;;
        --token=*)     NODE_TOKEN="${1#*=}" ;;
        --token)       NODE_TOKEN="$2"; shift ;;
        --name=*)      NODE_NAME="${1#*=}" ;;
        --name)        NODE_NAME="$2"; shift ;;
        --location=*)  NODE_LOCATION="${1#*=}" ;;
        --location)    NODE_LOCATION="$2"; shift ;;
        --repo=*)      AGENT_REPO="${1#*=}" ;;
        --force)       FORCE=1 ;;
        --python=*)    PYTHON_BIN="${1#*=}" ;;
        -h|--help)
            sed -n '2,20p' "$0"; exit 0 ;;
        *) warn "unknown argument: $1" ;;
    esac
    shift
done

[[ -z "$PANEL_URL"    ]] && fail "--panel-url is required"
[[ -z "$NODE_TOKEN"   ]] && fail "--token is required"
[[ -z "$NODE_NAME"    ]] && NODE_NAME="$(hostname)"
[[ -z "$NODE_LOCATION" ]] && NODE_LOCATION="external"

# ── Privilege check ──────────────────────────────────────────────────────

if [[ $EUID -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
        exec sudo --preserve-env=PANEL_URL,NODE_TOKEN,NODE_NAME,NODE_LOCATION,AGENT_REPO,FORCE,PYTHON_BIN \
            bash "$0" "$@"
    else
        fail "must run as root (or with sudo available)"
    fi
fi

# ── Layout ──────────────────────────────────────────────────────────────

INSTALL_DIR="/opt/nosrat-node"
VENV_DIR="$INSTALL_DIR/venv"
CONFIG_DIR="/etc/nosrat-node"
CONFIG_FILE="$CONFIG_DIR/config.env"
SYSTEMD_UNIT="/etc/systemd/system/nosrat-node.service"

mkdir -p "$CONFIG_DIR"
chmod 0750 "$CONFIG_DIR"

# ── Detect package manager & python ──────────────────────────────────────

detect_pkg() {
    for pm in apt-get dnf yum apk; do
        if command -v "$pm" >/dev/null 2>&1; then
            printf '%s' "$pm"
            return 0
        fi
    done
    return 1
}

detect_python() {
    for cand in python3.12 python3.11 python3.10 python3.9 python3.8 python3; do
        if command -v "$cand" >/dev/null 2>&1; then
            local ver
            ver="$("$cand" -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
            if [[ "$ver" == "3."* ]] && [[ "${ver#3.}" -ge 8 ]]; then
                command -v "$cand"
                return 0
            fi
        fi
    done
    return 1
}

PKG="$(detect_pkg || true)"
PY="$( [[ -n "$PYTHON_BIN" ]] && echo "$PYTHON_BIN" || detect_python || true)"
[[ -z "$PKG" ]] && fail "no supported package manager found (need apt, dnf, yum or apk)"
[[ -z "$PY"  ]] && fail "python 3.8+ not found"
print "package manager: $PKG"
print "python:          $PY"

# ── Install OS dependencies ─────────────────────────────────────────────

print "installing system packages"
case "$PKG" in
    apt-get)
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y -qq python3 python3-venv python3-pip ca-certificates curl
        ;;
    dnf|yum)
        "$PKG" -y install python3 python3-pip ca-certificates curl
        ;;
    apk)
        apk add --no-cache python3 py3-pip ca-certificates curl bash
        ;;
esac

# ── Fetch agent bundle ──────────────────────────────────────────────────

print "downloading agent bundle"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL "$AGENT_REPO/node-agent/agent.py"          -o "$TMP/agent.py"
curl -fsSL "$AGENT_REPO/node-agent/requirements.txt"   -o "$TMP/requirements.txt"
curl -fsSL "$AGENT_REPO/node-agent/nosrat-node"        -o "$TMP/nosrat-node" || true
curl -fsSL "$AGENT_REPO/node-agent/README.md"          -o "$TMP/README.md" || true

if [[ -s "$TMP/nosrat-node" ]]; then
    chmod 0755 "$TMP/nosrat-node"
fi

mkdir -p "$INSTALL_DIR"
cp -f "$TMP/agent.py"        "$INSTALL_DIR/agent.py"
cp -f "$TMP/requirements.txt" "$INSTALL_DIR/requirements.txt"
[[ -s "$TMP/nosrat-node" ]] && cp -f "$TMP/nosrat-node" "$INSTALL_DIR/nosrat-node"
[[ -s "$TMP/README.md"    ]] && cp -f "$TMP/README.md"    "$INSTALL_DIR/README.md"
chmod 0644 "$INSTALL_DIR/agent.py" "$INSTALL_DIR/requirements.txt"
[[ -x "$INSTALL_DIR/nosrat-node" ]] && chmod 0755 "$INSTALL_DIR/nosrat-node"

# ── Recreate venv if forced ─────────────────────────────────────────────

if [[ "$FORCE" == "1" && -d "$VENV_DIR" ]]; then
    print "removing existing venv (--force)"
    rm -rf "$VENV_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
    print "creating python venv at $VENV_DIR"
    "$PY" -m venv "$VENV_DIR"
fi

print "installing python dependencies"
"$VENV_DIR/bin/pip" install --upgrade pip wheel >/dev/null
"$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# ── Write config.env ────────────────────────────────────────────────────

print "writing $CONFIG_FILE"
umask 077
cat >"$CONFIG_FILE" <<EOF
# nosrat-node configuration (managed by install.sh — do not edit by hand)
PANEL_URL=${PANEL_URL}
NODE_TOKEN=${NODE_TOKEN}
NODE_NAME=${NODE_NAME}
NODE_LOCATION=${NODE_LOCATION}
PYTHON_BIN=$VENV_DIR/bin/python
EOF
chmod 0600 "$CONFIG_FILE"

# ── systemd unit ────────────────────────────────────────────────────────

print "installing systemd unit"
cat >"$SYSTEMD_UNIT" <<'UNIT'
[Unit]
Description=nosrat-panel node agent
Documentation=https://github.com/pdnczone/Nosrat-Panel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/etc/nosrat-node/config.env
ExecStart=/opt/nosrat-node/venv/bin/python /opt/nosrat-node/agent.py
Restart=always
RestartSec=5
LimitNOFILE=65535
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 "$SYSTEMD_UNIT"

# ── Enable & start ──────────────────────────────────────────────────────

if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload
    systemctl enable nosrat-node.service
    systemctl restart nosrat-node.service
    sleep 1
    if systemctl is-active --quiet nosrat-node.service; then
        print "service started successfully"
    else
        warn "service is not active; check 'journalctl -u nosrat-node -n 50'"
    fi
else
    warn "systemctl not found; start the agent manually: $VENV_DIR/bin/python $INSTALL_DIR/agent.py"
fi

print "done."
print "  panel  : $PANEL_URL"
print "  node   : $NODE_NAME ($NODE_LOCATION)"
print "  config : $CONFIG_FILE"
print "  journal: journalctl -u nosrat-node -f"