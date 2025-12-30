#!/bin/bash
# Script to add t-aiops-01 lab server via API
# Usage: ./add_lab_server.sh

set -e

echo "===================================="
echo "Add t-aiops-01 Lab Server via API"
echo "===================================="
echo ""

# Configuration
API_URL="http://15.204.244.73:8080"
ADMIN_USER="admin"
ADMIN_PASS="Passw0rd"
LAB_HOSTNAME="15.204.233.209"
LAB_USER="ubuntu"
LAB_PASS="Passw0rd"

# Step 1: Login and get token
echo "Step 1: Authenticating..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}")

TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "❌ Error: Could not authenticate"
  echo "Response: $LOGIN_RESPONSE"
  exit 1
fi

echo "✓ Authentication successful"
echo ""

# Step 2: Add lab server
echo "Step 2: Adding t-aiops-01 lab server..."
ADD_RESPONSE=$(curl -s -X POST "$API_URL/api/server-credentials" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"name\": \"t-aiops-01 Lab Server\",
    \"hostname\": \"$LAB_HOSTNAME\",
    \"port\": 22,
    \"username\": \"$LAB_USER\",
    \"password\": \"$LAB_PASS\",
    \"os_type\": \"linux\",
    \"protocol\": \"ssh\",
    \"auth_type\": \"password\",
    \"environment\": \"test\",
    \"is_active\": true
  }")

# Check response
SERVER_ID=$(echo "$ADD_RESPONSE" | jq -r '.id')

if [ -z "$SERVER_ID" ] || [ "$SERVER_ID" = "null" ]; then
  echo "⚠️  Warning: Server may already exist or error occurred"
  echo "Response: $ADD_RESPONSE"
  
  # Check if it's a duplicate
  if echo "$ADD_RESPONSE" | grep -qi "already exists\|duplicate"; then
    echo ""
    echo "ℹ️  Lab server likely already configured"
    
    # Try to get existing server
    GET_RESPONSE=$(curl -s -X GET "$API_URL/api/server-credentials" \
      -H "Authorization: Bearer $TOKEN")
    
    EXISTING_ID=$(echo "$GET_RESPONSE" | jq -r '.[] | select(.hostname=="'$LAB_HOSTNAME'") | .id')
    
    if [ -n "$EXISTING_ID" ] && [ "$EXISTING_ID" != "null" ]; then
      SERVER_ID=$EXISTING_ID
      echo "Found existing server ID: $SERVER_ID"
    fi
  fi
else
  echo "✓ Lab server added successfully"
  echo "  Server ID: $SERVER_ID"
fi

echo ""

# Step 3: Test connection (if we have a server ID)
if [ -n "$SERVER_ID" ] && [ "$SERVER_ID" != "null" ]; then
  echo "Step 3: Testing connection to lab server..."
  TEST_RESPONSE=$(curl -s -X POST "$API_URL/api/server-credentials/$SERVER_ID/test" \
    -H "Authorization: Bearer $TOKEN")
  
  if echo "$TEST_RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
    echo "✓ Connection test successful!"
    echo "  Lab server is reachable and credentials are valid"
  else
    echo "❌ Connection test failed"
    echo "Response: $TEST_RESPONSE"
    echo ""
    echo "Please verify:"
    echo "  1. Lab server is running: ssh $LAB_USER@$LAB_HOSTNAME"
    echo "  2. Password is correct: $LAB_PASS"
    echo "  3. SSH is enabled on lab server"
  fi
fi

echo ""
echo "===================================="
echo "Configuration Complete"
echo "===================================="
echo ""
echo "Lab Server Details:"
echo "  • Name: t-aiops-01 Lab Server"
echo "  • Hostname: $LAB_HOSTNAME"
echo "  • Username: $LAB_USER"
echo "  • Environment: test"
echo ""
echo "Next Steps:"
echo "  1. Verify in UI: http://15.204.244.73:8080/settings"
echo "  2. Create test runbook targeting this server"
echo "  3. Execute runbook to validate end-to-end flow"
echo ""
