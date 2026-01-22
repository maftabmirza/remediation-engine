import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth_service import get_current_user
from app.models import User, LLMProvider

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_user():
    return User(id=1, username="testuser", role="admin")

@pytest.fixture
def override_auth(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides = {}

@pytest.fixture
def mock_db_provider():
    with patch("app.routers.revive.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Mock LLM Provider
        provider = LLMProvider(is_default=True, is_enabled=True)
        mock_db.query.return_value.filter.return_value.first.return_value = provider
        
        yield mock_db

def test_revive_chat_stream(client, override_auth):
    # We need to mock the Orchestrator inside the router
    # Since import happens inside the function, we patch 'app.services.revive.orchestrator.ReviveOrchestrator'
    # But wait, it's imported INSIDE the function: `from app.services.revive.orchestrator import ReviveOrchestrator`
    # Patching via sys.modules or patching where it is defined might be tricky if it's a local import.
    # However, `patch('app.services.revive.orchestrator.ReviveOrchestrator')` should work if done before the call.
    
    with patch("app.services.revive.orchestrator.ReviveOrchestrator") as MockOrchestrator, \
         patch("app.routers.revive.get_db") as mock_get_db: # We need to mock DB dependency too
         
        # Mock Orchestrator behavior
        mock_instance = MockOrchestrator.return_value
        
        async def mock_run_gen(msg, history, current_page=None, explicit_mode=None):
            yield "data: {\"type\": \"mode\", \"content\": \"grafana\"}\n\n"
            yield "Hello"
        
        mock_instance.run_revive_turn = mock_run_gen
        
        # Mock DB for LLM Provider check (step 1)
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        provider = LLMProvider(is_default=True, is_enabled=True)
        # Chain for query(LLMProvider).filter(...).first()
        mock_db.query.return_value.filter.return_value.first.return_value = provider
        
        # Mock Session creation
        # When creating session: db.add(), db.commit(), db.refresh()
        
        response = client.post(
            "/api/revive/chat/stream",
            json={"message": "test", "session_id": ""}
        )
        
        assert response.status_code == 200
        # StreamingResponse content is an iterator, TestClient allows iterating or getting text
        # But TestClient.post returns Response. For streaming, we might need stream=True
        
        # NOTE: TestClient fully buffers stream by default unless we use proper async client or similar.
        # But `response.text` should contain the concatenated stream.
        content = response.text
        assert "data: " in content
        assert "grafana" in content
        assert "Hello" in content # The chunk wrapped in data type chunk
        
        # Verify Orchestrator was called
        MockOrchestrator.assert_called_once()
