# TESTING STRATEGY & APPROACH

**Version**: 1.0
**Date**: 2025-12-29
**Purpose**: High-level testing approach to maintain quality without shipping test code to production

---

## CORE PRINCIPLE

**Production code should NEVER contain test code, test data, or test dependencies.**

Tests live in a separate structure and are excluded from production builds/deployments.

---

## 1. REPOSITORY STRUCTURE

### Recommended Directory Layout

```
remediation-engine/
├── app/                          # Production application code
│   ├── main.py
│   ├── models/
│   ├── routers/
│   ├── services/
│   └── schemas/
│
├── tests/                        # ✅ TEST CODE (excluded from production)
│   ├── __init__.py
│   ├── conftest.py              # pytest fixtures
│   ├── test_data/               # Test fixtures and data
│   │   ├── alerts/
│   │   ├── runbooks/
│   │   └── users.json
│   │
│   ├── unit/                    # Unit tests
│   │   ├── test_rules_engine.py
│   │   ├── test_remediation.py
│   │   └── test_auth.py
│   │
│   ├── integration/             # Integration tests
│   │   ├── test_alert_flow.py
│   │   ├── test_runbook_execution.py
│   │   └── test_knowledge_base.py
│   │
│   ├── api/                     # API endpoint tests
│   │   ├── test_alerts_api.py
│   │   ├── test_remediation_api.py
│   │   ├── test_chat_api.py
│   │   └── test_dashboard_api.py
│   │
│   ├── e2e/                     # End-to-end tests
│   │   ├── test_alert_to_remediation.py
│   │   └── test_dashboard_workflow.py
│   │
│   ├── performance/             # Load/stress tests
│   │   ├── test_alert_ingestion.py
│   │   └── test_concurrent_runbooks.py
│   │
│   └── security/                # Security tests
│       ├── test_authentication.py
│       ├── test_authorization.py
│       └── test_injection.py
│
├── .github/
│   └── workflows/
│       ├── ci.yml               # CI pipeline (runs tests)
│       ├── deploy-staging.yml   # Deploy to staging
│       └── deploy-prod.yml      # Deploy to production
│
├── docker/
│   ├── Dockerfile               # Production image
│   └── Dockerfile.test          # Test environment image
│
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # ✅ Test dependencies (NOT in production)
├── pytest.ini                   # pytest configuration
├── .dockerignore                # Exclude tests/ from Docker images
├── .gitignore
└── README.md
```

---

## 2. DEPENDENCY SEPARATION

### Production Dependencies (`requirements.txt`)
```txt
fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
pydantic==2.5.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
# ... production only
```

### Test Dependencies (`requirements-dev.txt`)
```txt
# Include production dependencies
-r requirements.txt

# Testing frameworks
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-xdist==3.5.0         # Parallel test execution

# API testing
httpx==0.25.2               # FastAPI test client
requests==2.31.0

# Mocking
pytest-mock==3.12.0
faker==20.1.0               # Generate fake test data
factory-boy==3.3.0          # Test fixtures

# Load testing
locust==2.20.0              # Performance testing

# Security testing
bandit==1.7.5               # Security linter
safety==2.3.5               # Dependency vulnerability scanner

# Code quality
black==23.12.1              # Code formatter
ruff==0.1.8                 # Linter
mypy==1.7.1                 # Type checker

# Coverage reporting
coverage[toml]==7.3.3
```

**Installation**:
```bash
# Production
pip install -r requirements.txt

# Development/Testing
pip install -r requirements-dev.txt
```

---

## 3. EXCLUDE TESTS FROM PRODUCTION

### 3.1 Docker Configuration

**`.dockerignore`**:
```
tests/
*.test.py
test_*.py
pytest.ini
requirements-dev.txt
.pytest_cache/
htmlcov/
.coverage
*.pyc
__pycache__/
.git/
.github/
docs/
*.md
```

**Production Dockerfile**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy only production requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only application code (tests/ excluded by .dockerignore)
COPY app/ ./app/

# Run production server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Test Dockerfile** (separate):
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy all requirements including dev
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy everything including tests
COPY . .

# Run tests
CMD ["pytest", "tests/", "-v", "--cov=app"]
```

---

### 3.2 Git Configuration

**`.gitignore`**:
```
# Test artifacts
.pytest_cache/
.coverage
htmlcov/
*.cover
.tox/
coverage.xml
*.log

# Test results
test-results/
junit.xml

# But DO commit test code
# tests/ is NOT in .gitignore
```

---

## 4. TESTING TOOLS & FRAMEWORKS

### 4.1 Test Framework: **pytest**

**Why pytest?**
- Industry standard for Python
- Rich plugin ecosystem
- Easy fixture management
- Excellent assertion introspection
- Parallel execution support

**Configuration** (`pytest.ini`):
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --strict-markers
    --cov=app
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    api: API tests
    e2e: End-to-end tests
    slow: Slow running tests
    security: Security tests
```

**Running tests**:
```bash
# All tests
pytest

# Specific category
pytest -m unit
pytest -m api
pytest -m "not slow"

# Specific file
pytest tests/api/test_alerts_api.py

# Parallel execution
pytest -n auto

# With coverage
pytest --cov=app --cov-report=html
```

---

### 4.2 API Testing: **httpx + FastAPI TestClient**

**Example**:
```python
# tests/api/test_alerts_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_alert():
    response = client.post("/webhook/alerts", json={
        "receiver": "remediation-engine",
        "status": "firing",
        "alerts": [...]
    })
    assert response.status_code == 200
```

---

### 4.3 Database Testing: **pytest fixtures + SQLAlchemy**

**Example**:
```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base

@pytest.fixture
def test_db():
    """Create a fresh test database for each test"""
    engine = create_engine("postgresql://test:test@localhost/test_db")
    Base.metadata.create_all(engine)

    TestSessionLocal = sessionmaker(bind=engine)
    db = TestSessionLocal()

    yield db

    db.close()
    Base.metadata.drop_all(engine)
```

---

### 4.4 Test Data: **Faker + Factory Boy**

**Example**:
```python
# tests/factories.py
from faker import Faker
import factory
from app.models import User

fake = Faker()

class UserFactory(factory.Factory):
    class Meta:
        model = User

    username = factory.LazyFunction(lambda: fake.user_name())
    email = factory.LazyFunction(lambda: fake.email())
    role = "operator"

# Usage in tests
def test_user_creation():
    user = UserFactory.build()
    assert user.username is not None
```

---

### 4.5 Performance Testing: **Locust**

**Separate repository or subdirectory**:
```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between

class RemediationEngineUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def ingest_alerts(self):
        self.client.post("/webhook/alerts", json={...})
```

**Run**:
```bash
locust -f tests/performance/locustfile.py --host=http://localhost:8000
```

---

### 4.6 Security Testing: **Bandit + Safety**

**Run as part of CI**:
```bash
# Security linting
bandit -r app/

# Dependency vulnerability scan
safety check -r requirements.txt
```

---

## 5. CI/CD PIPELINE APPROACH

### 5.1 GitHub Actions Workflow

**`.github/workflows/ci.yml`**:
```yaml
name: CI Pipeline

on:
  push:
    branches: [ main, develop, claude/* ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt

      - name: Run linting
        run: |
          ruff check app/
          black --check app/

      - name: Run security checks
        run: |
          bandit -r app/
          safety check -r requirements.txt

      - name: Run unit tests
        run: pytest tests/unit/ -v

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Run API tests
        run: pytest tests/api/ -v --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Build production Docker image
        run: |
          docker build -t remediation-engine:latest .

      - name: Verify tests excluded
        run: |
          docker run remediation-engine:latest ls -la
          # Should NOT see tests/ directory
```

---

### 5.2 Deployment Pipelines

**Staging** (with tests):
```yaml
name: Deploy to Staging

on:
  push:
    branches: [ develop ]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to staging environment
        run: |
          # Deploy code
          # Run smoke tests against staging
          pytest tests/e2e/ --host=https://staging.example.com
```

**Production** (NO test code):
```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]
    tags: [ 'v*' ]

jobs:
  deploy-production:
    runs-on: ubuntu-latest
    steps:
      - name: Build production image
        run: docker build -f Dockerfile -t remediation-engine:prod .

      - name: Push to registry
        run: docker push remediation-engine:prod

      - name: Deploy to production
        run: |
          # Deploy only production image (no tests)
          # Tests run BEFORE this in CI pipeline
```

---

## 6. TEST ENVIRONMENT STRATEGY

### 6.1 Environment Separation

| Environment | Purpose | Contains Tests? | Test Execution |
|-------------|---------|-----------------|----------------|
| **Local Dev** | Development | ✅ Yes | Run all tests locally |
| **CI/CD** | Automated testing | ✅ Yes (in CI runner) | Run on every commit |
| **Staging** | Pre-production validation | ❌ No (smoke tests run externally) | E2E tests against staging |
| **Production** | Live customer environment | ❌ **NEVER** | Monitoring only |

---

### 6.2 Test Data Management

**Approach 1: Fixtures in Code**
```python
# tests/test_data/alerts.json
{
  "sample_critical_alert": {...},
  "sample_warning_alert": {...}
}
```

**Approach 2: Database Seeding**
```python
# tests/fixtures/seed_data.py
def seed_test_database(db):
    # Create test users
    # Create test alerts
    # Create test runbooks
    pass
```

**Approach 3: Factory Pattern** (Recommended)
```python
# tests/factories.py
# Generate data on-demand
user = UserFactory.create()
alert = AlertFactory.create()
```

---

## 7. TESTING BEST PRACTICES

### 7.1 Test Isolation

**Each test should be independent:**
```python
# ✅ GOOD - Clean state
@pytest.fixture(autouse=True)
def setup_and_teardown(test_db):
    yield
    # Cleanup after each test
    test_db.query(Alert).delete()
    test_db.commit()

# ❌ BAD - Tests depend on each other
def test_create_user():
    user = create_user("test")  # Creates user

def test_delete_user():
    delete_user("test")  # Depends on previous test
```

---

### 7.2 Test Naming Convention

```python
# Format: test_<feature>_<scenario>_<expected_result>

def test_runbook_execution_with_approval_succeeds():
    pass

def test_runbook_execution_without_approval_fails():
    pass

def test_alert_ingestion_invalid_fingerprint_rejected():
    pass
```

---

### 7.3 AAA Pattern (Arrange-Act-Assert)

```python
def test_alert_analysis():
    # Arrange
    alert = create_test_alert()
    llm_provider = create_test_provider()

    # Act
    result = analyze_alert(alert, llm_provider)

    # Assert
    assert result.analyzed == True
    assert result.recommendations is not None
```

---

## 8. MONITORING TEST HEALTH

### 8.1 Test Metrics to Track

- **Code Coverage**: Target >80%
- **Test Execution Time**: <10 minutes for full suite
- **Flaky Tests**: <1% failure rate
- **Test Count Growth**: Track over time

### 8.2 Coverage Reports

**Generate HTML report**:
```bash
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

**Enforce minimum coverage**:
```ini
# pytest.ini
[pytest]
addopts = --cov-fail-under=80
```

---

## 9. RECOMMENDED WORKFLOW

### For Developers

```bash
# 1. Pull latest code
git pull origin develop

# 2. Install dev dependencies
pip install -r requirements-dev.txt

# 3. Write feature code in app/
# 4. Write tests in tests/

# 5. Run tests locally
pytest tests/unit/test_my_feature.py

# 6. Run all tests
pytest

# 7. Check coverage
pytest --cov=app

# 8. Commit (only if tests pass)
git add app/ tests/
git commit -m "Add feature X with tests"
git push
```

### For CI/CD

```
Push to GitHub
    ↓
GitHub Actions CI
    ├── Linting (ruff, black)
    ├── Security scan (bandit)
    ├── Unit tests
    ├── Integration tests
    ├── API tests
    └── Coverage check (80%+)
    ↓
All tests pass? ✅
    ↓
Build production Docker image (NO tests/)
    ↓
Deploy to Staging
    ↓
Run E2E smoke tests against staging
    ↓
Smoke tests pass? ✅
    ↓
Deploy to Production (ONLY app code)
```

---

## 10. ALTERNATIVE: SEPARATE TEST REPOSITORY (Optional)

### When to Consider

For **very large enterprises** with complex test infrastructure:

```
Repositories:
├── remediation-engine/           # Production code only
│   └── app/
│
└── remediation-engine-tests/     # Separate test repo
    ├── tests/
    ├── test-infrastructure/
    └── test-data/
```

**Pros**:
- Complete separation
- Different access controls
- Independent versioning

**Cons**:
- Harder to keep in sync
- More complex CI setup
- Version matching issues

**Recommendation**: Only if you have >10,000 tests or strict compliance requirements. Otherwise, single repo with good structure is better.

---

## 11. SUMMARY - HIGH-LEVEL APPROACH

### ✅ DO:
1. **Keep tests in `tests/` directory** (excluded from production)
2. **Separate dependencies**: `requirements.txt` vs `requirements-dev.txt`
3. **Use `.dockerignore`** to exclude tests from production images
4. **Run tests in CI/CD** before deployment
5. **Use pytest** as test framework
6. **Track code coverage** (target: 80%+)
7. **Automate everything** in CI pipeline

### ❌ DON'T:
1. **NEVER ship test code to production**
2. **NEVER include test dependencies in production**
3. **NEVER run tests in production environment**
4. **DON'T mix test code with app code**
5. **DON'T commit sensitive test credentials**

---

## 12. QUICK START CHECKLIST

- [ ] Create `tests/` directory structure
- [ ] Create `requirements-dev.txt` with pytest
- [ ] Add `.dockerignore` to exclude tests
- [ ] Configure `pytest.ini`
- [ ] Set up GitHub Actions CI pipeline
- [ ] Write first test
- [ ] Verify production Docker build excludes tests
- [ ] Set up coverage reporting
- [ ] Configure CI to fail if coverage <80%
- [ ] Document testing guidelines in README

---

## 13. TOOLS SUMMARY

| Purpose | Tool | Why |
|---------|------|-----|
| Test Framework | **pytest** | Industry standard, rich ecosystem |
| API Testing | **httpx / TestClient** | Built for FastAPI |
| Database Testing | **pytest fixtures** | Clean state per test |
| Test Data | **Faker / Factory Boy** | Generate realistic data |
| Performance | **Locust** | Scalable load testing |
| Security | **Bandit / Safety** | Automated security scanning |
| Coverage | **pytest-cov** | Track test coverage |
| CI/CD | **GitHub Actions** | Integrated with GitHub |
| Code Quality | **ruff / black** | Linting and formatting |

---

**END OF TESTING STRATEGY**

**Key Takeaway**: Tests live in `tests/` directory, never shipped to production. Use standard tools (pytest), automate in CI/CD, and enforce coverage.
