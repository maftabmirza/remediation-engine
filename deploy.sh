#!/bin/bash

# AIOps Platform Deployment Script
# Run this on your server to deploy the application

set -e

echo "=========================================="
echo "  AIOps Platform Deployment"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as proper user
if [ "$EUID" -eq 0 ]; then 
    echo -e "${YELLOW}Warning: Running as root. Consider using a non-root user.${NC}"
fi

# Check required tools
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Docker is required but not installed.${NC}" >&2; exit 1; }
command -v docker-compose >/dev/null 2>&1 || command -v docker compose >/dev/null 2>&1 || { echo -e "${RED}Docker Compose is required but not installed.${NC}" >&2; exit 1; }

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo ""
echo "Step 1: Checking environment file..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}Created .env from .env.example${NC}"
        echo -e "${RED}IMPORTANT: Edit .env file with your actual values before continuing!${NC}"
        echo ""
        echo "Required settings to update:"
        echo "  - POSTGRES_PASSWORD"
        echo "  - JWT_SECRET"
        echo "  - ADMIN_PASSWORD"
        echo "  - ANTHROPIC_API_KEY"
        echo ""
        read -p "Press Enter after editing .env file, or Ctrl+C to abort..."
    else
        echo -e "${RED}.env file not found and no .env.example to copy${NC}"
        exit 1
    fi
fi

echo ""
echo "Step 2: Creating required directories..."
mkdir -p static templates

echo ""
echo "Step 3: Checking Docker network..."
if ! docker network ls | grep -q "aiops_aiops-network"; then
    echo -e "${YELLOW}Creating aiops_aiops-network...${NC}"
    docker network create aiops_aiops-network 2>/dev/null || true
fi

echo ""
echo "Step 4: Stopping existing containers (if any)..."
docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true

echo ""
echo "Step 5: Building the application..."
docker compose build --no-cache 2>/dev/null || docker-compose build --no-cache

echo ""
echo "Step 6: Starting services..."
docker compose up -d 2>/dev/null || docker-compose up -d

echo ""
echo "Step 7: Waiting for services to be healthy..."
sleep 5

# Check if services are running
echo ""
echo "Checking service status..."
docker compose ps 2>/dev/null || docker-compose ps

# Wait for PostgreSQL
echo ""
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker exec aiops-postgres pg_isready -U aiops > /dev/null 2>&1; then
        echo -e "${GREEN}PostgreSQL is ready!${NC}"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Wait for app
echo ""
echo "Waiting for application to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "${GREEN}Application is ready!${NC}"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "=========================================="
echo -e "${GREEN}  Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Access URLs:"
echo "  Web UI:     http://${SERVER_IP}:8080"
echo "  API Docs:   http://${SERVER_IP}:8080/docs"
echo "  Health:     http://${SERVER_IP}:8080/health"
echo ""
echo "Default credentials (change after first login):"
echo "  Username: admin"
echo "  Password: (from ADMIN_PASSWORD in .env)"
echo ""
echo "Webhook URL for Alertmanager:"
echo "  http://remediation-engine:8080/webhook/alerts"
echo ""
echo "View logs:"
echo "  docker logs -f remediation-engine"
echo ""
