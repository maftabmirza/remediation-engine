
import pytest
from httpx import AsyncClient
from app.main import app
from app.models import User
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.username = "testuser"
    user.role = "operator"
    # Add other needed attributes
    return user

@pytest.mark.asyncio
async def test_inquiry_query_endpoint(async_client, mock_user):
    # Mock authentication
    from app.services.auth_service import get_current_user
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    # Mock InquiryOrchestrator to avoid real DB/LLM calls
    from app.services.agentic.inquiry_orchestrator import InquiryResponse
    
    mock_response = InquiryResponse(
         session_id=uuid4(),
         answer="Test Answer",
         tools_used=["test_tool"]
    )
    
    with patch("app.routers.inquiry.InquiryOrchestrator") as MockOrchestrator:
        instance = MockOrchestrator.return_value
        instance.process_query = AsyncMock(return_value=mock_response)
        
        response = await async_client.post("/api/v1/inquiry/query", json={"query": "test"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Test Answer"
        assert data["tools_used"] == ["test_tool"]
    
    # Clean up
    app.dependency_overrides = {}

@pytest.mark.asyncio
async def test_inquiry_suggestions(async_client, mock_user):
    from app.services.auth_service import get_current_user
    app.dependency_overrides[get_current_user] = lambda: mock_user
    
    response = await async_client.get("/api/v1/inquiry/suggestions")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
    app.dependency_overrides = {}
