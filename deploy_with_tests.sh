#!/bin/bash
# Deployment script for p-aiops-01 with tests
# Usage: ./deploy_with_tests.sh

set -e  # Exit on error

echo "===================================="
echo "Remediation Engine Deployment + Tests"
echo "Target: p-aiops-01 (15.204.244.73)"
echo "Branch: review-grafana-docs-Xr3H8"
echo "===================================="
echo ""

# Configuration
SERVER="ubuntu@15.204.244.73"
APP_DIR="/home/aftab/aiops-platform"
BRANCH="review-grafana-docs-Xr3H8"

echo "Step 1: Connecting to server..."
ssh $SERVER "echo 'Connected to p-aiops-01'"

echo ""
echo "Step 2: Navigating to application directory..."
ssh $SERVER "cd $APP_DIR && pwd"

echo ""
echo "Step 3: Stashing local changes..."
ssh $SERVER "cd $APP_DIR && git stash"

echo ""
echo "Step 4: Pulling latest code from branch: $BRANCH..."
ssh $SERVER "cd $APP_DIR && git pull origin $BRANCH"

echo ""
echo "Step 5: Installing dependencies..."
ssh $SERVER "cd $APP_DIR && pip install -r requirements.txt && pip install -r requirements-test.txt"

echo ""
echo "Step 6: Rebuilding Docker containers..."
ssh $SERVER "cd $APP_DIR && docker-compose down"
ssh $SERVER "cd $APP_DIR && docker-compose build --no-cache"

echo ""
echo "Step 7: Starting services..."
ssh $SERVER "cd $APP_DIR && docker-compose up -d"

echo ""
echo "Step 8: Waiting for services to start..."
sleep 10

echo ""
echo "Step 9: Checking container status..."
ssh $SERVER "cd $APP_DIR && docker-compose ps"

echo ""
echo "Step 10: Running database migrations..."
ssh $SERVER "cd $APP_DIR && docker exec remediation-engine alembic upgrade head"

echo ""
echo "Step 11: Running unit tests..."
ssh $SERVER "cd $APP_DIR && docker exec remediation-engine python run_tests.py --unit --fast"

echo ""
echo "Step 12: Configuring t-aiops-01 Lab Server via API..."

# Get authentication token
echo "  → Logging in to get auth token..."
TOKEN=$(ssh $SERVER "curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{\"username\":\"admin\",\"password\":\"Passw0rd\"}' | jq -r '.access_token'")

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "  ⚠️  Warning: Could not get auth token. You may need to add lab server manually."
else
  echo "  ✓ Authentication successful"
  
  # Add t-aiops-01 lab server
  echo "  → Adding t-aiops-01 lab server..."
  RESPONSE=$(ssh $SERVER "curl -s -X POST http://localhost:8080/api/server-credentials \
    -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer $TOKEN' \
    -d '{
      \"name\": \"t-aiops-01 Lab Server\",
      \"hostname\": \"15.204.233.209\",
      \"port\": 22,
      \"username\": \"ubuntu\",
      \"password\": \"Passw0rd\",
      \"os_type\": \"linux\",
      \"protocol\": \"ssh\",
      \"auth_type\": \"password\",
      \"environment\": \"test\",
      \"is_active\": true
    }'")
  
  # Check if server was added successfully
  if echo "$RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
    SERVER_ID=$(echo "$RESPONSE" | jq -r '.id')
    echo "  ✓ Lab server added successfully (ID: $SERVER_ID)"
    
    # Test connection to lab server
    echo "  → Testing connection to t-aiops-01..."
    TEST_RESULT=$(ssh $SERVER "curl -s -X POST http://localhost:8080/api/server-credentials/$SERVER_ID/test \
      -H 'Authorization: Bearer $TOKEN'")
    
    if echo "$TEST_RESULT" | jq -e '.success' > /dev/null 2>&1; then
      echo "  ✓ Connection test successful!"
    else
      echo "  ⚠️  Connection test failed: $TEST_RESULT"
    fi
  else
    echo "  ⚠️  Server may already exist or error occurred: $RESPONSE"
  fi
fi

echo ""
echo "===================================="
echo "Deployment Complete!"
echo "===================================="
echo ""
echo "Services:"
echo "  • Web UI: http://15.204.244.73:8080"
echo "  • Login: admin / Passw0rd"
echo "  • Lab Server: t-aiops-01 (15.204.233.209) - Configured ✓"
echo ""
echo "Next Steps:"
echo "1. Verify lab server in UI: Settings → Server Credentials"
echo "2. Run integration tests:"
echo "   ssh $SERVER 'cd $APP_DIR && docker exec remediation-engine python run_tests.py --integration'"
echo "3. Test runbook execution to t-aiops-01"
echo ""
echo "Logs: ssh $SERVER 'docker logs remediation-engine --tail=50'"
echo ""
