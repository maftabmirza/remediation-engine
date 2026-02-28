
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import get_current_user
from app.models import User
from uuid import uuid4

client = TestClient(app)

# Mock User Models
def create_mock_user(role_name):
    return User(
        id=uuid4(),
        username=f"test_{role_name}",
        email=f"{role_name}@example.com",
        role=role_name,
        is_active=True
    )

@pytest.mark.asyncio
async def test_pii_logs_access_security_viewer():
    # Arrange
    user = create_mock_user("security_viewer")
    app.dependency_overrides[get_current_user] = lambda: user
    
    # Act
    response = client.get("/api/v1/pii/logs")
    
    # Assert
    assert response.status_code == 200
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_pii_logs_access_admin():
    # Arrange
    user = create_mock_user("admin")
    app.dependency_overrides[get_current_user] = lambda: user
    
    # Act
    response = client.get("/api/v1/pii/logs")
    
    # Assert
    assert response.status_code == 200
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_pii_logs_deny_viewer():
    # Arrange
    user = create_mock_user("viewer")
    app.dependency_overrides[get_current_user] = lambda: user
    
    # Act
    response = client.get("/api/v1/pii/logs")
    
    # Assert
    assert response.status_code == 403
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_pii_feedback_access_operator():
    # Arrange
    user = create_mock_user("operator")
    app.dependency_overrides[get_current_user] = lambda: user
    
    # Act
    response = client.post("/api/v1/pii/feedback/false-positive", json={
        "log_id": str(uuid4()),
        "reason": "Test reason"
    })
    
    # Assert
    assert response.status_code != 403
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_pii_feedback_deny_viewer():
    # Arrange
    user = create_mock_user("viewer")
    app.dependency_overrides[get_current_user] = lambda: user
    
    # Act
    response = client.post("/api/v1/pii/feedback/false-positive", json={
        "log_id": str(uuid4()),
        "reason": "Test reason"
    })
    
    # Assert
    assert response.status_code == 403
    
    app.dependency_overrides.clear()
