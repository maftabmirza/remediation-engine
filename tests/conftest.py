"""
Pytest configuration and shared fixtures for the AIOps Remediation Engine test suite.
"""
import os
import sys
import pytest
from typing import Generator, AsyncGenerator
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import will be done lazily to avoid initialization issues
try:
    from app.database import Base, get_db
    from app.main import app
except ImportError:
    # If imports fail, tests will handle it
    Base = None
    get_db = None
    app = None


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_db_engine():
    """Create a test database engine using PostgreSQL.
    
    Uses the existing PostgreSQL container from docker-compose.
    Falls back to environment variable TEST_DATABASE_URL if set.
    """
    # Use test database URL from environment or default to docker-compose postgres
    test_db_url = os.environ.get(
        "TEST_DATABASE_URL",
        os.environ.get(
            "DATABASE_URL",
            "postgresql://aiops:aiops_secure_password@localhost:5432/aiops_test"
        )
    )
    
    # Ensure we're using a test database (not production)
    if "test" not in test_db_url:
        # Append _test to database name for safety
        test_db_url = test_db_url.replace("/aiops", "/aiops_test")
    
    engine = create_engine(test_db_url, echo=False)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Clean up - drop all data but keep schema for speed
    with engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()
    
    engine.dispose()



@pytest.fixture(scope="function")
def test_db_session(test_db_engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine
    )
    
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def test_client(test_db_session) -> Generator[TestClient, None, None]:
    """Create a FastAPI test client with test database."""
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


# ============================================================================
# Authentication Fixtures
# ============================================================================

@pytest.fixture
def mock_jwt_token():
    """Mock JWT token for authenticated requests."""
    return "mock_jwt_token_for_testing"


@pytest.fixture
def admin_user_data():
    """Sample admin user data."""
    return {
        "username": "admin",
        "email": "admin@example.com",
        "full_name": "Admin User",
        "role": "admin",
        "is_active": True
    }


@pytest.fixture
def regular_user_data():
    """Sample regular user data."""
    return {
        "username": "user",
        "email": "user@example.com",
        "full_name": "Regular User",
        "role": "operator",
        "is_active": True
    }


# ============================================================================
# Alert Fixtures
# ============================================================================

@pytest.fixture
def sample_alert_payload():
    """Sample Alertmanager webhook payload."""
    return {
        "receiver": "remediation-engine",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "NginxDown",
                    "severity": "critical",
                    "instance": "web-server-01",
                    "job": "nginx-exporter"
                },
                "annotations": {
                    "summary": "Nginx is down on web-server-01",
                    "description": "Nginx service has stopped responding"
                },
                "startsAt": "2025-01-15T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "fingerprint": "abc123def456"
            }
        ],
        "groupLabels": {"alertname": "NginxDown"},
        "commonLabels": {
            "alertname": "NginxDown",
            "severity": "critical"
        },
        "commonAnnotations": {},
        "externalURL": "http://alertmanager:9093"
    }


@pytest.fixture
def sample_alert_data():
    """Sample alert data for database."""
    return {
        "alert_name": "NginxDown",
        "severity": "critical",
        "instance": "web-server-01",
        "job": "nginx-exporter",
        "status": "firing",
        "summary": "Nginx is down on web-server-01",
        "description": "Nginx service has stopped responding"
    }


# ============================================================================
# Rule Fixtures
# ============================================================================

@pytest.fixture
def sample_rule_data():
    """Sample auto-analyze rule data."""
    return {
        "name": "Auto-analyze critical alerts",
        "description": "Automatically analyze all critical alerts",
        "priority": 1,
        "alert_name_pattern": "*",
        "severity_pattern": "critical",
        "instance_pattern": "*",
        "job_pattern": "*",
        "action": "auto_analyze",
        "enabled": True
    }


@pytest.fixture
def sample_wildcard_rule():
    """Sample rule with wildcard pattern."""
    return {
        "name": "Production alerts",
        "alert_name_pattern": "prod-*",
        "severity_pattern": "*",
        "instance_pattern": "*",
        "job_pattern": "*",
        "action": "auto_analyze",
        "enabled": True,
        "priority": 10
    }


@pytest.fixture
def sample_json_logic_rule():
    """Sample rule with JSON logic condition."""
    return {
        "name": "Complex condition rule",
        "condition_json": {
            "and": [
                {"==": [{"var": "severity"}, "critical"]},
                {"in": [{"var": "instance"}, ["prod-db-01", "prod-db-02"]]}
            ]
        },
        "alert_name_pattern": "*",
        "severity_pattern": "*",
        "instance_pattern": "*",
        "job_pattern": "*",
        "action": "auto_analyze",
        "enabled": True,
        "priority": 1
    }


# ============================================================================
# LLM Provider Fixtures
# ============================================================================

@pytest.fixture
def sample_llm_provider():
    """Sample LLM provider configuration."""
    return {
        "name": "Claude Test",
        "provider_type": "anthropic",
        "model_id": "claude-3-sonnet-20240229",
        "is_default": True,
        "is_enabled": True,
        "config_json": {
            "temperature": 0.3,
            "max_tokens": 2000
        }
    }


@pytest.fixture
def mock_llm_response():
    """Mock LLM analysis response."""
    return {
        "root_cause": "Nginx service crashed due to configuration error",
        "impact": "Web application is unavailable to users",
        "immediate_actions": [
            "Check Nginx error logs",
            "Verify configuration syntax",
            "Restart Nginx service"
        ],
        "remediation_steps": [
            "1. SSH to web-server-01",
            "2. Run: sudo nginx -t",
            "3. Run: sudo systemctl restart nginx",
            "4. Run: sudo systemctl status nginx"
        ]
    }


# ============================================================================
# Runbook Fixtures
# ============================================================================

@pytest.fixture
def sample_runbook_data():
    """Sample runbook data."""
    return {
        "name": "Restart Nginx Service",
        "description": "Standard procedure to restart Nginx",
        "enabled": True,
        "auto_execute": False,
        "approval_required": True,
        "timeout_seconds": 300,
        "steps": [
            {
                "name": "Check Nginx status",
                "order": 1,
                "command": "systemctl status nginx",
                "executor_type": "ssh",
                "timeout_seconds": 30
            },
            {
                "name": "Restart Nginx",
                "order": 2,
                "command": "sudo systemctl restart nginx",
                "executor_type": "ssh",
                "timeout_seconds": 60
            },
            {
                "name": "Verify Nginx is running",
                "order": 3,
                "command": "systemctl is-active nginx",
                "executor_type": "ssh",
                "timeout_seconds": 30
            }
        ]
    }


# ============================================================================
# Server Fixtures
# ============================================================================

@pytest.fixture
def sample_server_credentials():
    """Sample server credentials."""
    return {
        "name": "Test Server",
        "hostname": "test-server-01",
        "port": 22,
        "username": "testuser",
        "os_type": "linux",
        "protocol": "ssh",
        "auth_type": "key",
        "environment": "test"
    }


# ============================================================================
# Mock Service Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_service():
    """Mock LLM service."""
    mock = MagicMock()
    mock.analyze_alert = AsyncMock(return_value={
        "root_cause": "Test root cause",
        "impact": "Test impact",
        "immediate_actions": ["Action 1", "Action 2"],
        "remediation_steps": ["Step 1", "Step 2"]
    })
    return mock


@pytest.fixture
def mock_ssh_service():
    """Mock SSH service."""
    mock = MagicMock()
    mock.connect = AsyncMock(return_value=True)
    mock.execute_command = AsyncMock(return_value=("Success output", "", 0))
    mock.disconnect = AsyncMock()
    return mock


@pytest.fixture
def mock_rules_engine():
    """Mock rules engine."""
    mock = MagicMock()
    mock.match_rule = MagicMock(return_value=True)
    mock.evaluate_alert = MagicMock(return_value="auto_analyze")
    return mock


# ============================================================================
# Environment Fixtures
# ============================================================================

@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://aiops:aiops_secure_password@localhost:5432/aiops_test")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://aiops:aiops_secure_password@localhost:5432/aiops_test")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")


# ============================================================================
# Async Fixtures
# ============================================================================

@pytest.fixture
async def async_test_client() -> AsyncGenerator:
    """Create an async test client."""
    from httpx import AsyncClient
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# ============================================================================
# Cleanup Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks before each test."""
    yield
    # Cleanup happens here if needed


@pytest.fixture(autouse=True)
def isolate_tests():
    """Ensure tests are isolated from each other."""
    yield
    # Any cleanup needed between tests
