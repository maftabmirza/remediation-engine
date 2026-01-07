import pytest
import sys
import os

# Ensure app is in path
sys.path.append('/app')

# PROACTIVE: Import ALL models to ensure SQLAlchemy registry is populated
# This fixture runs before any test execution to prevent InvalidRequestError
@pytest.fixture(scope="session", autouse=True)
def load_all_models():
    print("Loading all models for registry...")
    try:
        from app.models import User, Role
        import app.models_agent
        import app.models_ai_helper
        import app.models_application
        import app.models_chat
        import app.models_dashboards
        import app.models_group
        import app.models_itsm
        import app.models_knowledge
        import app.models_learning
        import app.models_remediation
        import app.models_runbook_acl
        import app.models_scheduler
        import app.models_troubleshooting
        import app.models_observability
    except ImportError as e:
        print(f"Warning: Some imports failed during conftest setup: {e}")

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
