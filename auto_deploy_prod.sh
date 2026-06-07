#!/bin/bash
# Deploy to p-aiops-01 (15.204.244.73)

SERVER="ubuntu@15.204.244.73"
BRANCH="claude/review-grafana-docs-xr3h8-PDXto"

echo "========================================"
echo "Deploying to Production ($SERVER)"
echo "Branch: $BRANCH"
echo "========================================"

# SSH command
ssh -o StrictHostKeyChecking=no $SERVER "
  set -e
  
  # Find directory
  if [ -d \"/aiops\" ]; then
    cd /aiops
  elif [ -d \"/home/ubuntu/remediation-engine\" ]; then
    cd /home/ubuntu/remediation-engine
  elif [ -d \"/home/ubuntu/aiops-platform\" ]; then
    cd /home/ubuntu/aiops-platform
  else
    echo \"❌ Error: Could not find application directory!\"
    exit 1
  fi
  
  echo \"✅ Connected. Working directory: \$(pwd)\"
  
  echo \"🔄 Step 1: Git Pull\"
  git fetch origin
  git checkout $BRANCH || git checkout -b $BRANCH origin/$BRANCH
  git pull origin $BRANCH
  
  echo \"🐳 Step 2: Rebuild Container\"
  docker compose up -d --build remediation-engine
  
  echo \"⏳ Step 3: Waiting for startup...\"
  sleep 10
  
  echo \"🔍 Step 4: Container Status\"
  docker ps | grep remediation-engine
  
  echo \"📜 Step 5: Recent Logs\"
  docker logs remediation-engine --tail 50

  echo "🧪 Step 6: Deploy Verification"
  if command -v python3 >/dev/null 2>&1; then
    python3 scripts/verify_deploy.py --mode "\${AIOPS_DEPLOY_VERIFY_MODE:-warn}" --base-url "http://localhost:8080"
  else
    echo "⚠️ Warning: python3 not available; skipping deploy verification"
  fi
"
