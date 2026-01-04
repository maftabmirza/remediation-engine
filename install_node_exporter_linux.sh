#!/bin/bash
set -e

# Version to install
VERSION="1.7.0"
ARCH="amd64"
OS="linux"
DOWNLOAD_URL="https://github.com/prometheus/node_exporter/releases/download/v${VERSION}/node_exporter-${VERSION}.${OS}-${ARCH}.tar.gz"
INSTALL_DIR="/usr/local/bin"
USER="node_exporter"

echo "=== Installing node_exporter v${VERSION} ==="

# Create user if not exists
if ! id "$USER" &>/dev/null; then
    sudo useradd --no-create-home --shell /bin/false $USER
    echo "Created user $USER"
fi

# Download and install
echo "Downloading $DOWNLOAD_URL..."
if command -v wget >/dev/null 2>&1; then
    wget -qO /tmp/node_exporter.tar.gz "$DOWNLOAD_URL"
elif command -v curl >/dev/null 2>&1; then
    curl -L -o /tmp/node_exporter.tar.gz "$DOWNLOAD_URL"
else
    echo "Error: Neither wget nor curl found. Please install one of them."
    exit 1
fi

tar -xf /tmp/node_exporter.tar.gz -C /tmp
sudo mv /tmp/node_exporter-${VERSION}.${OS}-${ARCH}/node_exporter "$INSTALL_DIR/"
rm -rf /tmp/node_exporter*
echo "Installed node_exporter to $INSTALL_DIR"

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<EOF
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=$USER
Group=$USER
Type=simple
ExecStart=$INSTALL_DIR/node_exporter

[Install]
WantedBy=multi-user.target
EOF

# Reload and start
sudo systemctl daemon-reload
sudo systemctl enable --now node_exporter
echo "node_exporter started and enabled."
systemctl status node_exporter --no-pager
