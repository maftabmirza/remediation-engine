#!/bin/bash
#
# AIOps Platform - First-time deployment script
# Sets up all services including MCP Grafana integration
#
# Usage: ./scripts/deploy-first-time.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           AIOps Platform - First-Time Deployment             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Step 1: Check prerequisites
echo -e "${YELLOW}[1/6] Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v curl &> /dev/null; then
    echo -e "${RED}curl is not installed. Please install curl first.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites met${NC}"

# Step 2: Setup environment file
echo -e "${YELLOW}[2/6] Setting up environment...${NC}"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env from .env.example${NC}"
        echo -e "${YELLOW}  Please review and update .env with your settings${NC}"
    else
        echo -e "${RED}No .env.example found. Cannot proceed.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Step 3: Pull images
echo -e "${YELLOW}[3/6] Pulling Docker images...${NC}"
docker compose pull 2>&1 | grep -E "(Pulling|Downloaded|up to date)" || true
echo -e "${GREEN}✓ Images pulled${NC}"

# Step 4: Start core services (without mcp-grafana first)
echo -e "${YELLOW}[4/6] Starting core services...${NC}"
docker compose up -d postgres prometheus loki tempo mimir alertmanager promtail grafana 2>&1 | tail -5
echo -e "${GREEN}✓ Core services started${NC}"

# Step 5: Wait for Grafana and setup MCP
echo -e "${YELLOW}[5/6] Setting up MCP Grafana integration...${NC}"

echo -n "  Waiting for Grafana to be healthy..."
max_attempts=30
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -sf "http://localhost:3000/api/health" > /dev/null 2>&1; then
        echo -e " ${GREEN}Ready!${NC}"
        break
    fi
    echo -n "."
    sleep 3
    ((attempt++))
done

if [ $attempt -gt $max_attempts ]; then
    echo -e " ${RED}Timeout!${NC}"
    echo -e "${YELLOW}  Grafana is not responding. Continuing without MCP setup.${NC}"
    echo -e "${YELLOW}  Run './scripts/setup-mcp-grafana.sh' manually later.${NC}"
else
    # Run MCP Grafana setup
    if [ -x "$SCRIPT_DIR/setup-mcp-grafana.sh" ]; then
        "$SCRIPT_DIR/setup-mcp-grafana.sh"
    else
        echo -e "${YELLOW}  MCP setup script not found. Skipping.${NC}"
    fi
fi

# Step 6: Start all remaining services
echo -e "${YELLOW}[6/6] Starting all services...${NC}"
docker compose up -d 2>&1 | tail -5
echo -e "${GREEN}✓ All services started${NC}"

# Summary
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗"
echo -e "║                    Deployment Complete!                        ║"
echo -e "╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Services Status:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "aiops|mcp|remediation" | head -15
echo ""
echo -e "${GREEN}Access URLs:${NC}"
echo -e "  • AIOps Platform: http://localhost:8080"
echo -e "  • Grafana Direct: http://localhost:3000"
echo -e "  • Prometheus:     http://localhost:9090"
echo -e "  • MCP Grafana:    http://localhost:8001/sse"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo -e "  1. Update .env with your LLM API keys (ANTHROPIC_API_KEY, etc.)"
echo -e "  2. Access the platform at http://localhost:8080"
echo -e "  3. Login with admin credentials from .env"
echo ""
