#!/bin/bash
# Deploy updated code to server and restart

echo "========================================="
echo "Deploying Alert Trigger Fix to Server"
echo "========================================="
echo ""

# Server details
SERVER="aftab@172.234.217.11"
APP_DIR="/home/aftab/aiops-platform"

echo "Step 1: SSH to server and pull latest code..."
ssh $SERVER << 'ENDSSH'
  cd /home/aftab/aiops-platform
  
  echo "Current directory: $(pwd)"
  echo ""
  
  echo "Step 2: Pull latest code from git..."
  git pull origin codex/suggest-improvements-for-dashboard-ux
  
  echo ""
  echo "Step 3: Rebuild and restart containers..."
  docker-compose down remediation-engine
  docker-compose up --build -d remediation-engine
  
  echo ""
  echo "Step 4: Wait for container to start..."
  sleep 5
  
  echo ""
  echo "Step 5: Check container status..."
  docker ps | grep remediation-engine
  
  echo ""
  echo "Step 6: Check logs for any errors..."
  docker logs remediation-engine --tail 50
  
ENDSSH

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Next: Fire the test alert again to verify the fix"
echo "Run: python fire_test_alert.py"
echo ""
