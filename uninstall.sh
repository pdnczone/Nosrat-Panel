#!/usr/bin/env bash
# Nosrat Panel - Complete Uninstaller
# Usage: sudo bash uninstall.sh

set -euo pipefail

echo "🧹 Nosrat Panel - Complete Uninstall"
echo "===================================="

# 1. Stop and remove Docker containers
echo "[1/8] Stopping Docker containers..."
docker compose -f /opt/nosrat-panel/docker-compose.yml down -v 2>/dev/null || true
docker compose -f /opt/nosrat-panel/node/docker-compose.yml down -v 2>/dev/null || true

# Also check for any running nosrat containers
docker ps -a --filter "name=nosrat" --format "{{.Names}}" | xargs -r docker rm -f 2>/dev/null || true

# 2. Remove Docker images
echo "[2/8] Removing Docker images..."
docker images --filter "reference=nosrat*" --format "{{.Repository}}:{{.Tag}}" | xargs -r docker rmi -f 2>/dev/null || true

# 3. Remove systemd services
echo "[3/8] Removing systemd services..."
systemctl stop nosrat-panel 2>/dev/null || true
systemctl disable nosrat-panel 2>/dev/null || true
systemctl stop nosrat-node 2>/dev/null || true
systemctl disable nosrat-node 2>/dev/null || true

rm -f /etc/systemd/system/nosrat-panel.service
rm -f /etc/systemd/system/nosrat-node.service
systemctl daemon-reload

# 4. Remove CLI tools
echo "[4/8] Removing CLI tools..."
rm -f /usr/local/bin/nosrat
rm -f /usr/local/bin/nosrat-node

# 5. Remove config directories
echo "[5/8] Removing configuration directories..."
rm -rf /etc/nosrat
rm -rf /etc/nosrat-node
rm -rf /opt/nosrat-panel
rm -rf /var/lib/nosrat
rm -rf /var/log/nosrat

# 6. Remove Nginx config
echo "[6/8] Removing Nginx configuration..."
rm -f /etc/nginx/sites-enabled/nosrat
rm -f /etc/nginx/sites-available/nosrat
nginx -t && systemctl reload nginx 2>/dev/null || true

# 7. Remove SSL certificates (Let's Encrypt)
echo "[7/8] Removing SSL certificates..."
certbot delete --cert-name nosrat 2>/dev/null || true

# 8. Remove firewall rules (optional - comment out if you want to keep)
echo "[8/8] Cleaning up firewall rules..."
ufw delete allow 8000/tcp 2>/dev/null || true
ufw delete allow 8888/tcp 2>/dev/null || true
ufw delete allow 443/tcp 2>/dev/null || true

echo ""
echo "✅ Nosrat Panel completely removed!"
echo ""
echo "Note: Docker, Nginx, and Certbot are NOT removed (they may be used by other services)."
echo "To remove them too: apt remove docker.io docker-compose nginx certbot"