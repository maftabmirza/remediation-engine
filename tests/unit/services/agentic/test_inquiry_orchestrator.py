
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from app.services.agentic.inquiry_orchestrator import InquiryOrchestrator, InquiryResponse
from app.models import User, LLMProvider

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = uuid4()
    return user

@pytest.fixture
def mock_provider():
    provider = MagicMock(spec=LLMProvider)
    return provider

@pytest.fixture
def mock_permission_service():
    return MagicMock()

@pytest.fixture
def mock_registry():
    registry = MagicMock()
    registry.get_tools.return_value = [MagicMock(name="tool1"), MagicMock(name="tool2")]
    return registry

@pytest.fixture
def orchestrator(mock_db, mock_user, mock_provider, mock_permission_service, mock_registry):
    return InquiryOrchestrator(
        db=mock_db,
        user=mock_user,
        provider=mock_provider,
        permission_service=mock_permission_service,
        registry=mock_registry
    )

@pytest.mark.asyncio
async def test_process_query_success(orchestrator, mock_permission_service, mock_registry):
    # Setup
    mock_permission_service.can_access_pillar.return_value = True
    mock_permission_service.filter_tools_by_permission.return_value = mock_registry.get_tools()
    
    # Mock NativeToolAgent response
    mock_response_obj = MagicMock()
    mock_response_obj.content = "The answer is 42."
    mock_response_obj.tool_calls_made = ["tool1"]

    # Mock NativeToolAgent
    with patch("app.services.agentic.inquiry_orchestrator.NativeToolAgent") as MockAgentClass:
        mock_agent_instance = MockAgentClass.return_value
        mock_agent_instance.run = AsyncMock(return_value=mock_response_obj)
        
        # Execute
        response = await orchestrator.process_query("What is the answer?", session_id=uuid4())
        
        # Verify
        assert isinstance(response, InquiryResponse)
        assert response.answer == "The answer is 42."
        assert response.tools_used == ["tool1"]
        assert response.error is None
        
        # Check permissions called
        mock_permission_service.can_access_pillar.assert_called_with(orchestrator.user, "inquiry")
        
        # Check Agent instantiation
        MockAgentClass.assert_called()
        call_kwargs = MockAgentClass.call_args.kwargs
        assert call_kwargs['db'] == orchestrator.db
        assert call_kwargs['provider'] == orchestrator.provider

@pytest.mark.asyncio
async def test_process_query_denied(orchestrator, mock_permission_service):
    # Setup
    mock_permission_service.can_access_pillar.return_value = False
    
    # Mock default provider lookup since we might hit that check first? 
    # Actually code checks provider first (step 0), then permission (step 1).
    # Our fixture provides a provider so step 0 passes.
    
    # Execute
    response = await orchestrator.process_query("What is the answer?")
    
    # Verify
    assert response.error == "AccessDenied"
    assert "Access denied" in response.answer

@pytest.mark.asyncio
async def test_process_query_error(orchestrator, mock_permission_service):
    # Setup
    mock_permission_service.can_access_pillar.return_value = True
    
    # Mock NativeToolAgent to raise exception
    with patch("app.services.agentic.inquiry_orchestrator.NativeToolAgent") as MockAgentClass:
        mock_agent_instance = MockAgentClass.return_value
        mock_agent_instance.run = AsyncMock(side_effect=Exception("LLM Error"))
        
        # Execute
        response = await orchestrator.process_query("What is the answer?")
        
        # Verify
        assert "LLM Error" in response.error
        assert "encountered an error" in response.answer

@pytest.mark.asyncio
async def test_process_query_no_provider(mock_db, mock_user, mock_permission_service, mock_registry):
    # Orchestrator without provider
    orchestrator = InquiryOrchestrator(
        db=mock_db,
        user=mock_user,
        provider=None, # No provider passed
        permission_service=mock_permission_service,
        registry=mock_registry
    )
    
    # Mock get_default_provider to return None
    with patch("app.services.agentic.inquiry_orchestrator.get_default_provider", return_value=None):
        response = await orchestrator.process_query("Hello")
        
        assert response.error == "ConfigurationError"
        assert "No LLM provider configured" in response.answer
