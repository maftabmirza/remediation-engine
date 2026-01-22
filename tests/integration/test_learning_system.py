import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models import SolutionOutcome
from app.services.embedding_service import EmbeddingService

# Helper to mock embedding service
@pytest.fixture
def mock_embedding_service():
    with patch("app.routers.feedback.EmbeddingService") as MockService:
        instance = MockService.return_value
        instance.is_configured.return_value = True
        # Return a dummy 1536-dim vector matching OpenAIs format
        instance.generate_embedding.return_value = [0.1] * 1536
        yield instance

def test_submit_solution_feedback_happy_path(
    test_client: TestClient, 
    test_db_session: Session, 
    admin_auth_headers: dict,
    mock_embedding_service
):
    """
    Test successful feedback submission with auto-generated embeddings.
    """
    payload = {
        "solution_type": "agent_suggestion",
        "solution_reference": "Run sudo systemctl restart nginx",
        "problem_description": "Nginx is down with 502 error",
        "success": True,
        "user_feedback": "Worked perfectly"
    }
    
    response = test_client.post(
        "/api/v1/solution-feedback",
        json=payload,
        headers=admin_auth_headers
    )
    
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["message"] == "Feedback recorded successfully"
    
    # Verify DB record
    outcome = test_db_session.query(SolutionOutcome).filter_by(id=data["id"]).first()
    assert outcome is not None
    assert outcome.problem_description == payload["problem_description"]
    assert outcome.success is True
    assert outcome.solution_type == "agent_suggestion"
    
    # Verify embedding was generated (mocked)
    assert outcome.problem_embedding is not None
    assert len(outcome.problem_embedding) == 1536
    assert outcome.problem_embedding[0] == 0.1

def test_submit_feedback_validation_error(
    test_client: TestClient, 
    admin_auth_headers: dict
):
    """
    Test validation error when required fields are missing.
    """
    # Missing solution_reference
    payload = {
        "solution_type": "agent_suggestion",
        "success": True
    }
    
    response = test_client.post(
        "/api/v1/solution-feedback",
        json=payload,
        headers=admin_auth_headers
    )
    
    assert response.status_code == 422

def test_submit_feedback_no_embedding_service_configured(
    test_client: TestClient, 
    test_db_session: Session, 
    admin_auth_headers: dict
):
    """
    Test feedback works even if embedding service fails or is not configured.
    """
    with patch("app.routers.feedback.EmbeddingService") as MockService:
        instance = MockService.return_value
        instance.is_configured.return_value = False # Simulate not configured
        
        payload = {
            "solution_type": "command",
            "solution_reference": "ls -la",
            "problem_description": "List files",
            "success": False,
            "user_feedback": "Did not help"
        }
        
        response = test_client.post(
            "/api/v1/solution-feedback",
            json=payload,
            headers=admin_auth_headers
        )
        
        assert response.status_code == 201
        
        # Verify DB record exists but has no embedding
        data = response.json()
        outcome = test_db_session.query(SolutionOutcome).filter_by(id=data["id"]).first()
        assert outcome is not None
        assert outcome.problem_embedding is None
