# Testing Quick Start Guide

This guide will help you quickly set up and run tests for the AIOps Remediation Engine.

## Prerequisites

- Python 3.11 or higher
- pip (Python package installer)
- Virtual environment (recommended)

## Quick Setup (5 minutes)

### 1. Install Test Dependencies

```bash
# From the project root directory
pip install -r requirements-test.txt
```

### 2. Run Your First Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test category
pytest tests/unit -v
```

### 3. Check Coverage

```bash
# Run tests with coverage report
pytest --cov=app --cov-report=html

# Open coverage report in browser
# On macOS:
open htmlcov/index.html

# On Linux:
xdg-open htmlcov/index.html

# On Windows:
start htmlcov/index.html
```

## Common Test Commands

### Run Specific Tests

```bash
# Run tests in a specific file
pytest tests/unit/services/test_rules_engine.py

# Run a specific test class
pytest tests/unit/services/test_rules_engine.py::TestMatchPattern

# Run a specific test function
pytest tests/unit/services/test_rules_engine.py::TestMatchPattern::test_wildcard_matches_everything

# Run tests matching a pattern
pytest -k "wildcard"
```

### Run Tests by Category

```bash
# Unit tests only (fast)
pytest tests/unit

# Integration tests only
pytest tests/integration

# End-to-end tests only
pytest tests/e2e
```

### Run Tests with Different Output

```bash
# Minimal output
pytest -q

# Verbose output
pytest -v

# Extra verbose output
pytest -vv

# Show print statements
pytest -s

# Show local variables on failure
pytest -l
```

### Run Tests in Parallel

```bash
# Use all CPU cores
pytest -n auto

# Use specific number of cores
pytest -n 4
```

## Understanding Test Results

### Successful Test Output

```
tests/unit/services/test_rules_engine.py::TestMatchPattern::test_wildcard_matches_everything PASSED [100%]

====================== 1 passed in 0.05s ======================
```

### Failed Test Output

```
tests/unit/services/test_rules_engine.py::TestMatchPattern::test_exact_match FAILED

=========================== FAILURES ===========================
_________ TestMatchPattern.test_exact_match ___________

    def test_exact_match(self):
        """Test exact string matching."""
>       assert match_pattern("HighCPU", "HighCPU") is True
E       AssertionError: assert False is True

tests/unit/services/test_rules_engine.py:45: AssertionError
====================== 1 failed in 0.10s ======================
```

## Test Structure Overview

```
tests/
├── conftest.py              # Shared fixtures (users, alerts, etc.)
├── unit/                    # Fast, isolated tests
│   └── services/           # Service layer tests
│       ├── test_rules_engine.py    # Rules matching tests
│       └── test_llm_service.py     # LLM integration tests
├── integration/            # API endpoint tests
│   ├── test_alerts_api.py
│   └── test_auth_api.py
└── e2e/                    # Complete workflow tests
    └── test_alert_workflow.py
```

## Common Fixtures

These are automatically available in all tests (defined in `conftest.py`):

- `test_db_session` - Database session for testing
- `test_client` - FastAPI test client
- `sample_alert_payload` - Example Alertmanager webhook data
- `sample_rule_data` - Example auto-analyze rule
- `admin_user_data` - Admin user credentials
- `mock_llm_service` - Mocked LLM service

### Using Fixtures

```python
def test_with_fixtures(test_client, sample_alert_payload):
    """Test using fixtures."""
    response = test_client.post("/api/alerts/webhook", json=sample_alert_payload)
    assert response.status_code in [200, 202]
```

## Debugging Tests

### Run Tests with Python Debugger

```bash
# Drop into debugger on failure
pytest --pdb

# Drop into debugger at start of each test
pytest --trace
```

### Show Print Statements

```bash
# Show print() output
pytest -s

# Show logging output
pytest --log-cli-level=DEBUG
```

### Run Only Failed Tests

```bash
# Rerun only failed tests from last run
pytest --lf

# Run failed tests first, then others
pytest --ff
```

## Writing Your First Test

### 1. Create Test File

```bash
# Create a new test file
touch tests/unit/test_my_feature.py
```

### 2. Write Test

```python
# tests/unit/test_my_feature.py
import pytest

class TestMyFeature:
    def test_basic_functionality(self):
        """Test basic functionality."""
        result = 2 + 2
        assert result == 4
    
    def test_with_fixture(self, sample_alert_data):
        """Test using a fixture."""
        assert sample_alert_data["alert_name"] == "NginxDown"
```

### 3. Run Your Test

```bash
pytest tests/unit/test_my_feature.py -v
```

## CI/CD Integration

Tests automatically run on:
- Every push to main/develop branches
- Every pull request
- GitHub Actions workflow: `.github/workflows/tests.yml`

### Local Pre-commit Testing

```bash
# Run the same tests that CI runs
pytest tests/unit tests/integration -v --cov=app
```

## Troubleshooting

### "Module not found" Error

```bash
# Ensure you're in the project root
cd /path/to/remediation-engine

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt
```

### "No tests collected"

```bash
# Check test discovery pattern
pytest --collect-only

# Ensure test files start with "test_"
# Ensure test functions start with "test_"
```

### Database Errors

Tests use SQLite in-memory database by default. If you see database errors:

```python
# Check conftest.py database fixtures
# Ensure SQLAlchemy models are imported correctly
```

### Import Errors

```bash
# Ensure app module is in Python path
export PYTHONPATH="${PYTHONPATH}:${PWD}"

# Or run from project root
cd /path/to/remediation-engine
pytest
```

## Next Steps

1. **Read Full Documentation**: See `tests/README.md` for detailed information
2. **Review Test Plan**: See `TESTING_PLAN.md` for comprehensive test scenarios
3. **Write More Tests**: Add tests for new features
4. **Check Coverage**: Aim for 80%+ coverage

## Quick Reference

| Command | Description |
|---------|-------------|
| `pytest` | Run all tests |
| `pytest -v` | Run with verbose output |
| `pytest -k "pattern"` | Run tests matching pattern |
| `pytest tests/unit` | Run unit tests only |
| `pytest --cov=app` | Run with coverage |
| `pytest --lf` | Rerun failed tests |
| `pytest -n auto` | Run in parallel |
| `pytest -s` | Show print output |
| `pytest --pdb` | Debug on failure |

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [Coverage.py Guide](https://coverage.readthedocs.io/)

## Getting Help

- Check `tests/README.md` for detailed documentation
- Review example tests in `tests/unit/services/`
- Look at fixtures in `tests/conftest.py`
- Consult `TESTING_PLAN.md` for test scenarios

Happy Testing! 🚀
