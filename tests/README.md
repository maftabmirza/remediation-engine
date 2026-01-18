# AIOps Remediation Engine - Test Suite

This directory contains the comprehensive test suite for the AIOps Remediation Engine. Tests are organized by type and follow pytest best practices for testing Python/FastAPI applications.

## Test Structure

```
tests/
├── conftest.py                          # Shared fixtures and pytest configuration
├── unit/                                # Unit tests (fast, isolated)
│   ├── services/                        # Service layer tests
│   │   └── test_rules_engine.py         # Rules engine pattern matching
│   ├── models/                          # Model validation tests
│   ├── utils/                           # Utility function tests
│   ├── test_grafana_branding.py         # Grafana white-labeling tests
│   └── test_templates.py                # Template rendering tests
├── integration/                         # Integration tests (require DB)
│   ├── test_alerts_api.py               # Alerts API endpoints
│   ├── test_alerts_rigorous.py          # Comprehensive alert testing
│   ├── test_auth_api.py                 # Authentication API
│   ├── test_clustering_integration.py   # Alert clustering
│   └── test_runbook_views.py            # Runbook view endpoints
├── e2e/                                 # End-to-end workflow tests
│   └── test_alert_workflow.py           # Complete alert handling
├── security/                            # Security-focused tests
├── performance/                         # Performance/load tests
├── fixtures/                            # Test data fixtures
├── test_analytics_service.py            # Analytics service tests
├── test_application_profiles_api.py     # Application profiles tests
├── test_grafana_datasources_api.py      # Grafana datasources tests
├── test_loki_client.py                  # Loki client tests
└── test_tempo_client.py                 # Tempo client tests
```

## Quick Start

### Install Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Tests

```bash
pytest
```

### Run Tests with Coverage

```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html

# View report
open htmlcov/index.html      # macOS
xdg-open htmlcov/index.html  # Linux
```

## Running Specific Tests

### By Category

```bash
# Unit tests only
pytest tests/unit -v

# Integration tests only
pytest tests/integration -v

# End-to-end tests only
pytest tests/e2e -v

# Security tests only
pytest tests/security -v
```

### By Marker

```bash
# Run tests with specific markers
pytest -m unit
pytest -m integration
pytest -m e2e
pytest -m security

# Exclude markers
pytest -m "not requires_db"
pytest -m "not slow"
```

### By File or Function

```bash
# Run specific test file
pytest tests/unit/services/test_rules_engine.py -v

# Run specific test class
pytest tests/unit/services/test_rules_engine.py::TestMatchPattern -v

# Run specific test function
pytest tests/unit/services/test_rules_engine.py::TestMatchPattern::test_wildcard_matches -v
```

## Test Markers

Tests use pytest markers for categorization:

| Marker | Description |
|--------|-------------|
| `@pytest.mark.unit` | Fast, isolated unit tests |
| `@pytest.mark.integration` | Tests requiring database or external services |
| `@pytest.mark.e2e` | Full workflow end-to-end tests |
| `@pytest.mark.security` | Security-focused tests |
| `@pytest.mark.performance` | Performance and load tests |
| `@pytest.mark.slow` | Long-running tests |
| `@pytest.mark.asyncio` | Async tests |
| `@pytest.mark.requires_db` | Tests requiring database |
| `@pytest.mark.requires_llm` | Tests requiring LLM API access |
| `@pytest.mark.requires_ssh` | Tests requiring SSH connection |

## Fixtures

Common fixtures are defined in `conftest.py` and automatically available to all tests:

### Database Fixtures

```python
def test_with_database(test_db_session):
    """Uses SQLite in-memory database."""
    # test_db_session is automatically provided
    pass
```

### API Client Fixtures

```python
def test_api_endpoint(test_client):
    """Uses FastAPI TestClient."""
    response = test_client.get("/api/health")
    assert response.status_code == 200
```

### Authentication Fixtures

```python
def test_protected_endpoint(test_client, admin_token):
    """Uses pre-authenticated admin token."""
    response = test_client.get(
        "/api/admin/settings",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
```

## Test Configuration

### pytest.ini

Configuration in the project root includes:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = -v --tb=short
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    security: Security tests
    slow: Slow tests
    requires_db: Requires database
    requires_llm: Requires LLM API
    requires_ssh: Requires SSH
```

### Environment Variables

Create `.env.test` for test-specific configuration:

```bash
DATABASE_URL=sqlite:///:memory:
JWT_SECRET_KEY=test-secret-key-for-testing
TESTING=true
```

## Writing Tests

### Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Unit Test Example

```python
import pytest
from app.services.rules_engine import match_pattern

class TestMatchPattern:
    """Tests for the rules engine pattern matching."""

    def test_wildcard_matches_everything(self):
        """Wildcard pattern should match any string."""
        assert match_pattern("*", "anything") is True
        assert match_pattern("*", "") is True

    def test_exact_match(self):
        """Exact pattern should match only identical strings."""
        assert match_pattern("HighCPU", "HighCPU") is True
        assert match_pattern("HighCPU", "LowMemory") is False

    def test_regex_pattern(self):
        """Regex patterns should work correctly."""
        assert match_pattern("High.*", "HighCPU") is True
        assert match_pattern("High.*", "LowMemory") is False
```

### Integration Test Example

```python
import pytest

class TestAlertsAPI:
    """Integration tests for alerts API."""

    def test_create_alert(self, test_client, test_db_session):
        """Test creating an alert via API."""
        response = test_client.post(
            "/api/alerts",
            json={
                "name": "TestAlert",
                "severity": "warning",
                "instance": "server-01"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "TestAlert"

    def test_webhook_receives_alert(self, test_client, sample_alert_payload):
        """Test Alertmanager webhook endpoint."""
        response = test_client.post(
            "/webhook/alerts",
            json=sample_alert_payload
        )
        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
```

### Async Test Example

```python
import pytest

@pytest.mark.asyncio
async def test_async_operation(test_db_session):
    """Test an async service function."""
    from app.services.llm_service import analyze_alert

    result = await analyze_alert(
        alert_name="HighCPU",
        severity="critical"
    )
    assert result is not None
```

## Test Categories

### Unit Tests (`tests/unit/`)

Fast, isolated tests for individual functions and classes:

- **Services**: Business logic tests
- **Models**: SQLAlchemy model validation
- **Utils**: Utility function tests
- **Templates**: Jinja2 template rendering

### Integration Tests (`tests/integration/`)

Tests requiring database or service interactions:

- **API Endpoints**: HTTP request/response testing
- **Database Operations**: CRUD operations
- **Service Integration**: Multi-service workflows

### End-to-End Tests (`tests/e2e/`)

Complete workflow tests:

- Alert ingestion to analysis
- Runbook creation to execution
- User authentication flows

### Security Tests (`tests/security/`)

Security-focused testing:

- Authentication bypass attempts
- Authorization validation
- Input sanitization
- SQL injection prevention

### Performance Tests (`tests/performance/`)

Load and performance testing:

- Response time benchmarks
- Concurrent user handling
- Database query performance

## Coverage Goals

| Category | Target | Description |
|----------|--------|-------------|
| **Overall** | 80%+ | Total codebase coverage |
| **Critical Paths** | 100% | Authentication, security, core business logic |
| **Service Layer** | 90%+ | Business logic services |
| **API Endpoints** | 85%+ | All REST endpoints |
| **Models** | 80%+ | Database model validation |

## Continuous Integration

Tests run automatically on:

- Every commit to feature branches
- Pull request creation/updates
- Before deployment to staging/production

See `.github/workflows/tests.yml` for CI configuration.

## Troubleshooting

### Import Errors

Ensure you're running from the project root:

```bash
cd /path/to/remediation-engine
pytest tests/
```

### Database Connection Errors

Tests use SQLite in-memory by default. Verify:

```python
# In conftest.py
DATABASE_URL = "sqlite:///:memory:"
```

### Async Test Failures

Ensure `pytest-asyncio` is installed and configured:

```bash
pip install pytest-asyncio
```

### Mock Not Working

Patch at the location where the function is used, not where it's defined:

```python
# Correct
@patch("app.routers.alerts.llm_service.analyze")

# Incorrect
@patch("app.services.llm_service.analyze")
```

## Best Practices

1. **Keep tests isolated** - Each test should be independent
2. **Use fixtures** - Avoid duplicating setup code
3. **Mock external services** - Don't make real API calls
4. **Test behavior, not implementation** - Focus on what, not how
5. **Use descriptive names** - Test names should describe what they test
6. **One assertion per test** - Keep tests focused
7. **Test edge cases** - Include error conditions and boundary values
8. **Clean up after tests** - Use fixtures with cleanup

## Related Documentation

- [TESTING_QUICKSTART.md](../TESTING_QUICKSTART.md) - Quick start guide
- [TESTING_PLAN.md](../TESTING_PLAN.md) - Comprehensive testing strategy
- [TEST_COVERAGE_ANALYSIS.md](../TEST_COVERAGE_ANALYSIS.md) - Coverage analysis
- [TEMPLATE_TESTING_README.md](./TEMPLATE_TESTING_README.md) - Template testing guide
