# Manual Deployment Steps for p-aiops-01

## Quick Deployment Guide

Since automated SSH from Windows can have issues, follow these manual steps directly on the server.

### Step 1: SSH to p-aiops-01

```bash
ssh ubuntu@15.204.244.73
```

### Step 2: Navigate to Application Directory

```bash
cd /home/aftab/aiops-platform
```

### Step 3: Update Code

```bash
# Stash any local changes
git stash

# Pull latest code
git pull origin review-grafana-docs-Xr3H8

# Check current branch
git branch
```

### Step 4: Install Dependencies

```bash
# Install test dependencies (if pip is available on host)
pip install -r requirements-test.txt

# Or install inside container later
```

### Step 5: Rebuild Containers

```bash
# Stop containers
docker-compose down

# Rebuild without cache
docker-compose build --no-cache

# Start services
docker-compose up -d

# Wait 10 seconds for startup
sleep 10

# Check status
docker-compose ps
```

### Step 6: Run Migrations

```bash
docker exec remediation-engine alembic upgrade head
```

### Step 7: Install Test Dependencies in Container

```bash
docker exec remediation-engine pip install -r requirements-test.txt
```

### Step 8: Run Unit Tests

```bash
# Run all unit tests
docker exec remediation-engine python run_tests.py --unit --fast

# Or run specific test file
docker exec remediation-engine pytest tests/unit/models/test_alert_model.py -v
```

### Step 9: Add Lab Server via API

```bash
# Get auth token
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Passw0rd"}' | jq -r '.access_token')

echo "Token: $TOKEN"

# Add lab server
curl -X POST http://localhost:8080/api/server-credentials \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "t-aiops-01 Lab Server",
    "hostname": "15.204.233.209",
    "port": 22,
    "username": "ubuntu",
    "password": "Passw0rd",
    "os_type": "linux",
    "protocol": "ssh",
    "auth_type": "password",
    "environment": "test",
    "is_active": true
  }' | jq '.'
```

### Step 10: Test Lab Server Connection

```bash
# Get server ID from previous response or query all servers
SERVER_ID=$(curl -s -X GET http://localhost:8080/api/server-credentials \
  -H "Authorization: Bearer $TOKEN" | jq -r '.[] | select(.hostname=="15.204.233.209") | .id')

echo "Server ID: $SERVER_ID"

# Test connection
curl -X POST "http://localhost:8080/api/server-credentials/$SERVER_ID/test" \
  -H "Authorization: Bearer $TOKEN" | jq '.'
```

### Step 11: Verify Deployment

```bash
# Check logs
docker logs remediation-engine --tail=50

# Check all containers
docker ps

# Access UI
echo "Web UI: http://15.204.244.73:8080"
echo "Login: admin / Passw0rd"
```

### Step 12: Run Integration Tests

```bash
# Run integration tests
docker exec remediation-engine python run_tests.py --integration

# Run API tests
docker exec remediation-engine python run_tests.py --api

# Run with coverage
docker exec remediation-engine python run_tests.py --coverage
```

---

## Quick Copy-Paste Commands

All commands in one block (copy and paste):

```bash
cd /home/aftab/aiops-platform && \
git stash && \
git pull origin review-grafana-docs-Xr3H8 && \
docker-compose down && \
docker-compose build --no-cache && \
docker-compose up -d && \
sleep 10 && \
docker exec remediation-engine alembic upgrade head && \
docker exec remediation-engine pip install -r requirements-test.txt && \
docker exec remediation-engine python run_tests.py --unit --fast
```

Add lab server:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"Passw0rd"}' | jq -r '.access_token') && \
curl -X POST http://localhost:8080/api/server-credentials -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"name":"t-aiops-01 Lab Server","hostname":"15.204.233.209","port":22,"username":"ubuntu","password":"Passw0rd","os_type":"linux","protocol":"ssh","auth_type":"password","environment":"test","is_active":true}' | jq '.'
```

---

## Troubleshooting

### If git pull fails:
```bash
git reset --hard origin/review-grafana-docs-Xr3H8
```

### If containers won't start:
```bash
docker-compose logs remediation-engine
docker-compose logs aiops-postgres
```

### If tests fail:
```bash
# Check Python version
docker exec remediation-engine python --version

# Check dependencies
docker exec remediation-engine pip list | grep pytest

# Run single test
docker exec remediation-engine pytest tests/unit/models/test_alert_model.py::TestAlertCreation::test_create_alert_with_required_fields -v
```

### If jq is not installed:
```bash
sudo apt-get update && sudo apt-get install -y jq
```

---

## Expected Results

✅ Git pull shows latest code from review-grafana-docs-Xr3H8  
✅ Docker containers rebuild successfully  
✅ Unit tests pass (200+ tests)  
✅ Lab server added via API  
✅ Web UI accessible at http://15.204.244.73:8080  
✅ Can login with admin/Passw0rd  
✅ Server credentials show t-aiops-01 in UI
