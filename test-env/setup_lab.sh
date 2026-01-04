#!/bin/bash
set -e

echo "=== Starting Lab Environment Setup ==="

# 1. Update and Install Dependencies
echo "--> Updating system..."
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release stress-ng

# 2. Install Docker (simpler method)
if ! command -v docker &> /dev/null; then
    echo "--> Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    # Add current user to docker group
    sudo usermod -aG docker $USER
    echo "    Docker installed."
else
    echo "    Docker already installed."
fi

# 3. Install Node Exporter (Systemd Service)
if ! systemctl is-active --quiet node_exporter; then
    echo "--> Installing Node Exporter..."
    wget https://github.com/prometheus/node_exporter/releases/download/v1.7.0/node_exporter-1.7.0.linux-amd64.tar.gz
    tar xvfz node_exporter-1.7.0.linux-amd64.tar.gz
    sudo mv node_exporter-1.7.0.linux-amd64/node_exporter /usr/local/bin/
    
    # Create User
    sudo useradd -rs /bin/false node_exporter

    # Create Service File
    cat <<EOF | sudo tee /etc/systemd/system/node_exporter.service
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable node_exporter
    sudo systemctl start node_exporter
    rm -rf node_exporter-1.7.0.linux-amd64*
    echo "    Node Exporter installed and started."
else
    echo "    Node Exporter already running."
fi

# 4. Start Docker Containers
echo "--> Starting Target Containers..."
sudo docker compose -f docker-compose.lab.yml up -d

echo "=== Setup Complete! ==="
echo "Node Exporter running on port 9100"
echo "Web Target running on port 8080"
echo "Redis Target running on port 6379"
