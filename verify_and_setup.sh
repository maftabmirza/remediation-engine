#!/bin/bash
# API Verification and Lab Server Setup Script
# Run this on p-aiops-01

echo "============================================"
echo "API Verification and Lab Server Setup"
echo "============================================"
echo ""

# Step 1: Verify application is running
echo "Step 1: Verifying application health..."
curl -s http://localhost:8080/docs > /dev/null && echo "✓ Application is running" || echo "✗ Application not responding"
echo ""

# Step 2: Login and get token
echo "Step 2: Authenticating..."
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Passw0rd"}' | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "✗ Authentication failed"
  exit 1
else
  echo "✓ Authentication successful"
  echo "  Token: ${TOKEN:0:20}..."
fi
echo ""

# Step 3: Add t-aiops-01 lab server
echo "Step 3: Adding t-aiops-01 lab server..."
ADD_RESPONSE=$(curl -s -X POST http://localhost:8080/api/servers \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "t-aiops-01 Lab Server",
    "hostname": "15.204.233.209",
    "port": 22,
    "username": "ubuntu",
    "password": "Passw0rd",
    "os_type": "linux",
    "protocol": "ssh"
  }')

echo "$ADD_RESPONSE" | jq '.'

SERVER_ID=$(echo "$ADD_RESPONSE" | jq -r '.id')

if [ -z "$SERVER_ID" ] || [ "$SERVER_ID" = "null" ]; then
  echo "⚠ Server add may have failed, checking if it already exists..."
  
  # Try to get existing server
  SERVERS=$(curl -s -X GET http://localhost:8080/api/servers \
    -H "Authorization: Bearer $TOKEN")
  
  SERVER_ID=$(echo "$SERVERS" | jq -r '.[] | select(.hostname=="15.204.233.209") | .id')
  
  if [ -n "$SERVER_ID" ] && [ "$SERVER_ID" != "null" ]; then
    echo "✓ Server already exists with ID: $SERVER_ID"
  else
    echo "✗ Could not add or find server"
    echo "Response: $ADD_RESPONSE"
    exit 1
  fi
else
  echo "✓ Server added successfully"
  echo "  Server ID: $SERVER_ID"
fi
echo ""

# Step 4: Test connection
echo "Step 4: Testing connection to lab server..."
TEST_RESPONSE=$(curl -s -X POST "http://localhost:8080/api/servers/$SERVER_ID/test" \
  -H "Authorization: Bearer $TOKEN")

echo "$TEST_RESPONSE" | jq '.'

if echo "$TEST_RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
  echo "✓ Connection test successful!"
else
  echo "⚠ Connection test result: $TEST_RESPONSE"
fi
echo ""

# Step 5: List all servers
echo "Step 5: Listing all configured servers..."
curl -s -X GET http://localhost:8080/api/servers \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | {id, name, hostname, os_type, protocol}'

echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Access UI: http://15.204.244.73:8080"
echo "  2. Verify server in Settings → Server Credentials"
echo "  3. Create and execute test runbook"
