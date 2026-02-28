#!/bin/bash
#
# Setup script for MCP Grafana integration
# Creates Grafana service account and token, updates .env file
#
# Usage: ./scripts/setup-mcp-grafana.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== MCP Grafana Setup Script ===${NC}"

# Configuration
GRAFANA_HOST="${GRAFANA_HOST:-localhost}"
GRAFANA_PORT="${GRAFANA_PORT:-3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-admin}"
ENV_FILE="${ENV_FILE:-.env}"
SERVICE_ACCOUNT_NAME="mcp-grafana"

GRAFANA_URL="http://${GRAFANA_HOST}:${GRAFANA_PORT}"

# Load existing .env if present
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE" 2>/dev/null || true
    GRAFANA_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-$GRAFANA_PASSWORD}"
fi

echo -e "${YELLOW}Grafana URL: ${GRAFANA_URL}${NC}"

# Function to wait for Grafana to be ready
wait_for_grafana() {
    echo -n "Waiting for Grafana to be ready..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -sf "${GRAFANA_URL}/api/health" > /dev/null 2>&1; then
            echo -e " ${GREEN}Ready!${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    echo -e " ${RED}Failed!${NC}"
    echo "Grafana is not responding at ${GRAFANA_URL}"
    echo "Make sure Grafana container is running: docker compose up -d grafana"
    exit 1
}

# Function to check if service account exists
check_service_account() {
    local response
    response=$(curl -sf -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
        "${GRAFANA_URL}/api/serviceaccounts/search?query=${SERVICE_ACCOUNT_NAME}" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        local count
        count=$(echo "$response" | grep -o '"totalCount":[0-9]*' | cut -d: -f2)
        if [ "$count" -gt 0 ]; then
            # Get the service account ID
            echo "$response" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2
            return 0
        fi
    fi
    return 1
}

# Function to create service account
create_service_account() {
    echo "Creating service account '${SERVICE_ACCOUNT_NAME}'..."
    
    local response
    response=$(curl -sf -X POST -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
        "${GRAFANA_URL}/api/serviceaccounts" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"${SERVICE_ACCOUNT_NAME}\",\"role\":\"Admin\",\"isDisabled\":false}" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        local sa_id
        sa_id=$(echo "$response" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
        echo -e "${GREEN}Service account created with ID: ${sa_id}${NC}"
        echo "$sa_id"
        return 0
    else
        echo -e "${RED}Failed to create service account${NC}"
        return 1
    fi
}

# Function to create token for service account
create_token() {
    local sa_id=$1
    echo "Creating token for service account ID ${sa_id}..."
    
    local response
    response=$(curl -sf -X POST -u "${GRAFANA_USER}:${GRAFANA_PASSWORD}" \
        "${GRAFANA_URL}/api/serviceaccounts/${sa_id}/tokens" \
        -H "Content-Type: application/json" \
        -d '{"name":"mcp-token"}' 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        local token
        token=$(echo "$response" | grep -o '"key":"[^"]*"' | cut -d'"' -f4)
        if [ -n "$token" ]; then
            echo -e "${GREEN}Token created successfully${NC}"
            echo "$token"
            return 0
        fi
    fi
    
    echo -e "${RED}Failed to create token${NC}"
    return 1
}

# Function to update .env file
update_env_file() {
    local token=$1
    
    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}Creating ${ENV_FILE} from .env.example${NC}"
        if [ -f ".env.example" ]; then
            cp .env.example "$ENV_FILE"
        else
            touch "$ENV_FILE"
        fi
    fi
    
    # Check if GRAFANA_SERVICE_ACCOUNT_TOKEN exists in .env
    if grep -q "^GRAFANA_SERVICE_ACCOUNT_TOKEN=" "$ENV_FILE"; then
        # Update existing value
        sed -i "s|^GRAFANA_SERVICE_ACCOUNT_TOKEN=.*|GRAFANA_SERVICE_ACCOUNT_TOKEN=${token}|" "$ENV_FILE"
        echo -e "${GREEN}Updated GRAFANA_SERVICE_ACCOUNT_TOKEN in ${ENV_FILE}${NC}"
    else
        # Add new value
        echo "" >> "$ENV_FILE"
        echo "# MCP Grafana Service Account Token (auto-generated)" >> "$ENV_FILE"
        echo "GRAFANA_SERVICE_ACCOUNT_TOKEN=${token}" >> "$ENV_FILE"
        echo -e "${GREEN}Added GRAFANA_SERVICE_ACCOUNT_TOKEN to ${ENV_FILE}${NC}"
    fi
}

# Function to restart mcp-grafana container
restart_mcp_grafana() {
    echo "Restarting mcp-grafana container..."
    
    if command -v docker &> /dev/null; then
        if docker ps -a --format '{{.Names}}' | grep -q "mcp-grafana"; then
            docker compose up -d mcp-grafana 2>/dev/null || docker-compose up -d mcp-grafana 2>/dev/null
            echo -e "${GREEN}MCP Grafana container restarted${NC}"
        else
            echo -e "${YELLOW}MCP Grafana container not found. Run 'docker compose up -d' to start all services${NC}"
        fi
    fi
}

# Main execution
main() {
    # Wait for Grafana
    wait_for_grafana
    
    # Check if service account already exists
    echo "Checking for existing service account..."
    local sa_id
    sa_id=$(check_service_account)
    
    if [ -n "$sa_id" ]; then
        echo -e "${YELLOW}Service account '${SERVICE_ACCOUNT_NAME}' already exists (ID: ${sa_id})${NC}"
        
        # Check if token is already in .env
        if grep -q "^GRAFANA_SERVICE_ACCOUNT_TOKEN=glsa_" "$ENV_FILE" 2>/dev/null; then
            echo -e "${GREEN}Token already configured in ${ENV_FILE}${NC}"
            echo -e "${YELLOW}If you need a new token, delete the service account in Grafana UI and run this script again${NC}"
            exit 0
        fi
        
        echo "Creating new token..."
    else
        # Create new service account
        sa_id=$(create_service_account)
        if [ -z "$sa_id" ]; then
            echo -e "${RED}Failed to create service account${NC}"
            exit 1
        fi
    fi
    
    # Create token
    local token
    token=$(create_token "$sa_id")
    
    if [ -z "$token" ]; then
        echo -e "${RED}Failed to create token${NC}"
        exit 1
    fi
    
    # Update .env file
    update_env_file "$token"
    
    # Restart mcp-grafana
    restart_mcp_grafana
    
    echo ""
    echo -e "${GREEN}=== Setup Complete ===${NC}"
    echo -e "Service Account: ${SERVICE_ACCOUNT_NAME}"
    echo -e "Token: ${token:0:20}..."
    echo ""
    echo -e "MCP Grafana is now configured to connect to Grafana."
    echo -e "Verify with: docker logs mcp-grafana"
}

main "$@"
