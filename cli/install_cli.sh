#!/bin/bash
# Install CLI tools globally

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Install nosrat (panel CLI)
sudo cp "$SCRIPT_DIR/nosrat.py" /usr/local/bin/nosrat
sudo chmod +x /usr/local/bin/nosrat
echo "Installed nosrat to /usr/local/bin/nosrat"

# Install nosrat-node (node CLI)
sudo cp "$SCRIPT_DIR/nosrat-node.py" /usr/local/bin/nosrat-node
sudo chmod +x /usr/local/bin/nosrat-node
echo "Installed nosrat-node to /usr/local/bin/nosrat-node"

# Make Python scripts executable
chmod +x /usr/local/bin/nosrat
chmod +x /usr/local/bin/nosrat-node

echo "CLI tools installed successfully!"

