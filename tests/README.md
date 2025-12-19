# AIOps Remediation Engine - Test Suite

This directory contains the comprehensive test suite for the AIOps Remediation Engine. The tests are organized by type and follow industry best practices for testing Python applications.

## Test Structure

```
tests/
├── conftest.py                 # Shared fixtures and pytest configuration
├── unit/                       # Unit tests for individual components
│   ├── services/              # Service layer tests
│   │   ├── test_rules_engine.py
│   │   └── test_llm_service.py
│   ├── utils/                 # Utility function tests
│   └── models/                # Model validation tests
├── integration/               # Integration tests
│   ├── test_alerts_api.py    # Alerts API endpoint tests
│   ├── test_auth_api.py      # Authentication API tests
│   └── test_rules_api.py     # Rules API tests
├── e2e/                       # End-to-end tests
│   └── test_alert_workflow.py # Complete workflow tests
├── security/                  # Security-focused tests
├── performance/              # Performance and load tests
└── fixtures/                 # Test data fixtures
```

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Run only unit tests
pytest tests/unit -m unit

# Run only integration tests
pytest tests/integration -m integration

# Run only end-to-end tests
pytest tests/e2e -m e2e

# Run security tests
pytest tests/security -m security
```

### Run Tests with Coverage

```bash
# Generate coverage report
pytest --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html  # On macOS
xdg-open htmlcov/index.html  # On Linux
```

### Run Specific Test Files

```bash
# Run specific test file
pytest tests/unit/services/test_rules_engine.py

# Run specific test class
pytest tests/unit/services/test_rules_engine.py::TestMatchPattern

# Run specific test function
pytest tests/unit/services/test_rules_engine.py::TestMatchPattern::test_wildcard_matches_everything
```

### Run Tests in Parallel

```bash
# Run tests across 4 CPU cores
pytest -n 4
```

### Run Tests with Verbose Output

```bash
pytest -v
pytest -vv  # Extra verbose
```

## Test Markers

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (require DB, external services)
- `@pytest.mark.e2e` - End-to-end tests (full workflow)
- `@pytest.mark.security` - Security-focused tests
- `@pytest.mark.performance` - Performance/load tests
- `@pytest.mark.slow` - Tests that take a long time
- `@pytest.mark.asyncio` - Async tests
- `@pytest.mark.requires_db` - Requires database
- `@pytest.mark.requires_llm` - Requires LLM API
- `@pytest.mark.requires_ssh` - Requires SSH connection

### Using Markers

```bash
# Run only fast unit tests
pytest -m unit

# Run tests that don't require external services
pytest -m "not requires_llm and not requires_ssh"

# Run only slow tests
pytest -m slow
```

## Writing Tests

### Test Naming Convention

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Example Unit Test

```python
import pytest
from app.services.rules_engine import match_pattern

class TestMatchPattern:
    def test_wildcard_matches_everything(self):
        """Test that '*' pattern matches any value."""
        assert match_pattern("*", "anything") is True
    
    def test_exact_match(self):
        """Test exact string matching."""
        assert match_pattern("HighCPU", "HighCPU") is True
        assert match_pattern("HighCPU", "LowMemory") is False
```

### Example Integration Test

```python
import pytest
from unittest.mock import patch

class TestAlertsAPI:
    def test_webhook_receives_alert(self, test_client, sample_alert_payload):
        """Test receiving alert via webhook."""
        response = test_client.post(
            "/api/alerts/webhook",
            json=sample_alert_payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
```

### Using Fixtures

Fixtures are defined in `conftest.py` and are automatically available to all tests:

```python
def test_with_database(test_db_session):
    """Test using database session fixture."""
    # test_db_session is automatically provided
    pass

def test_with_client(test_client):
    """Test using FastAPI test client."""
    response = test_client.get("/api/alerts")
    assert response.status_code in [200, 401]
```

## Test Configuration

### pytest.ini

Configuration is defined in `pytest.ini` at the project root:

- Test discovery patterns
- Coverage settings
- Markers
- Output formatting
- Asyncio mode

### Environment Variables

Test environment variables should be set in `.env.test`:

```bash
DATABASE_URL=sqlite:///:memory:
JWT_SECRET_KEY=test-secret-key
# etc.
```

## Continuous Integration

Tests are automatically run on:
- Every commit
- Pull requests
- Before deployment

### GitHub Actions Workflow

See `.github/workflows/tests.yml` for CI configuration.

## Coverage Goals

- Overall coverage: 80%+
- Critical paths: 100%
- Service layer: 90%+
- API endpoints: 85%+

## Troubleshooting

### Tests Fail Due to Missing Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-test.txt
```

### Database Connection Errors

Tests use SQLite in-memory database by default. If you see connection errors:
- Check that SQLAlchemy is installed
- Verify `conftest.py` database fixtures

### Import Errors

If tests can't import app modules:
- Ensure you're running pytest from project root
- Check PYTHONPATH is set correctly

### Mock Errors

If mocks aren't working:
- Ensure you're patching the correct import path
- Use `where it's used` not `where it's defined`

## Best Practices

1. **Keep tests isolated** - Each test should be independent
2. **Use fixtures** - Avoid duplicating setup code
3. **Mock external services** - Don't make real API calls
4. **Test behavior, not implementation** - Focus on what, not how
5. **Use descriptive names** - Test names should describe what they test
6. **Add docstrings** - Explain the test's purpose
7. **One assertion per test** - Keep tests focused
8. **Test edge cases** - Include error conditions and boundary values

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [Coverage.py](https://coverage.readthedocs.io/)

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Ensure tests pass locally
3. Check coverage doesn't decrease
4. Add appropriate markers
5. Update this README if needed

## Support

For questions or issues with tests:
- Check existing test examples
- Review conftest.py fixtures
- Consult TESTING_PLAN.md for detailed test scenarios
