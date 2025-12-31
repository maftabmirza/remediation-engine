# Quick Start Guide

Get the AIOps Test Management WebApp up and running in 5 minutes!

## Prerequisites

- Docker and Docker Compose installed
- 4GB free RAM
- Ports 8001 and 5433 available

## Step 1: Clone and Setup

```bash
# Clone repository
git clone https://github.com/maftabmirza/aiops-testing-webapp.git
cd test-webapp

# Copy environment file
cp .env.example .env
```

## Step 2: Start Services

```bash
# Start PostgreSQL and webapp
docker-compose up -d

# Wait for services to be ready (about 10 seconds)
docker-compose ps
```

Expected output:
```
NAME                STATUS
test-webapp-db      Up
test-webapp-app     Up
```

## Step 3: Initialize Database

```bash
# Create tables and seed test data
docker-compose exec webapp python scripts/init_db.py
```

Expected output:
```
==========================================
Test Management Database Initialization
==========================================
Creating database tables...
✓ Tables created successfully

Seeding test suites...
  + Linux Remediation Tests
  + Safety Mechanism Tests
  + Approval Workflow Tests
  + Windows Remediation Tests
✓ Created 4 test suites

Seeding test cases...
  + L01: High CPU Usage Remediation
  + L02: High Memory Usage Remediation
  + L03: Disk Space Cleanup
  + S01: Execution Rate Limiting
  + S02: Concurrent Execution Limit
  + S03: Dangerous Operation Prevention
✓ Created 6 test cases

==========================================
✓ Database initialization completed successfully!
==========================================
```

## Step 4: Access the Application

Open your browser and navigate to:

- **Dashboard**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs

## Step 5: Run Your First Test

### Via Web UI

1. Go to http://localhost:8001/test-cases
2. Click on test **L01: High CPU Usage Remediation**
3. Click **Run** button
4. View results in real-time at http://localhost:8001/test-runs

### Via Command Line

```bash
# Run a single test
docker-compose exec webapp ./scripts/run_tests.sh --test-id L01

# Run entire Linux suite
docker-compose exec webapp ./scripts/run_tests.sh --suite linux

# Run all tests
docker-compose exec webapp ./scripts/run_tests.sh
```

## Step 6: Explore Features

### Dashboard
- View test execution statistics
- See success rate trends
- Monitor active test runs

### Test Cases
- Browse all available tests
- Filter by category, priority, status
- Create new test cases

### Test Runs
- View execution history
- Filter by status
- Auto-refresh for active runs

## Common Commands

### View Logs
```bash
# Application logs
docker-compose logs -f webapp

# Database logs
docker-compose logs -f db
```

### Restart Services
```bash
# Restart all
docker-compose restart

# Restart webapp only
docker-compose restart webapp
```

### Stop Services
```bash
# Stop but keep data
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop and remove everything including volumes (CAUTION: destroys data)
docker-compose down -v
```

### Access Database
```bash
# PostgreSQL shell
docker-compose exec db psql -U aiops -d aiops_test_manager

# List tables
\dt

# Query test cases
SELECT test_id, name, priority FROM test_cases;
```

## Next Steps

### Add More Tests

Create a new test file in `tests/e2e/`:

```python
# tests/e2e/custom/test_my_feature.py
import pytest

@pytest.mark.C01
def test_C01_my_custom_test(api_client, auth_headers):
    """Custom test description"""
    print("[C01] Running custom test...")

    # Your test logic here
    response = api_client.get("/health")
    assert response.status_code == 200

    print("[C01] Test passed!")
```

Register in database:
```bash
docker-compose exec webapp python
>>> from app.database import AsyncSessionLocal
>>> from app.models import TestCase, TestSuite
>>> # Create test suite and test case
```

### Integrate with CI/CD

Add to `.github/workflows/test.yml`:

```yaml
name: E2E Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Start services
        run: docker-compose up -d

      - name: Initialize database
        run: docker-compose exec -T webapp python scripts/init_db.py

      - name: Run tests
        run: docker-compose exec -T webapp ./scripts/run_tests.sh
```

### Connect to Remediation Engine

Update `.env`:
```bash
REMEDIATION_ENGINE_URL=http://your-remediation-engine:8080
```

Restart services:
```bash
docker-compose restart webapp
```

## Troubleshooting

### Port Already in Use

Change ports in `docker-compose.yml`:
```yaml
services:
  webapp:
    ports:
      - "8002:8001"  # Change host port
  db:
    ports:
      - "5434:5432"  # Change host port
```

### Database Connection Error

Check database is running:
```bash
docker-compose ps db
docker-compose logs db
```

Reset database:
```bash
docker-compose down -v
docker-compose up -d
docker-compose exec webapp python scripts/init_db.py
```

### Tests Not Running

Check webapp logs:
```bash
docker-compose logs webapp
```

Verify pytest is working:
```bash
docker-compose exec webapp pytest --version
```

## Getting Help

- **Documentation**: See `README.md` for full documentation
- **API Docs**: http://localhost:8001/docs
- **Issues**: Report on GitHub
- **Logs**: `docker-compose logs -f`

## Clean Slate

To start fresh:
```bash
# Remove all containers, volumes, and images
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
docker-compose exec webapp python scripts/init_db.py
```

---

**You're all set!** 🎉

Visit http://localhost:8001 to start managing your tests.
