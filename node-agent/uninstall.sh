#!/usr/bin/env bash
# nosrat-node uninstaller — removes systemd unit, files and config.

set -Eeuo pipefail

INSTALL_DIR="/opt/nosrat-node"
CONFIG_DIR="/etc/nosrat-node"
SYSTEMD_UNIT="/etc/systemd/system/nosrat-node.service"

if [[ $EUID -ne 0 ]]; then
    if command -v sudo >/dev/null 2>&1; then
        exec sudo bash "$0" "$@"
    else
        echo "must run as root" >&2
        exit 1
    fi
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now nosrat-node.service 2>/dev/null || true
fi

rm -f "$SYSTEMD_UNIT"
rm -rf "$INSTALL_DIR" "$CONFIG_DIR"

if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload
    systemctl reset-failed nosrat-node.service 2>/dev/null || true
fi

echo "nosrat-node removed."