import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.revive.orchestrator import ReviveOrchestrator
from app.services.revive.mode_detector import ModeDetectionResult

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_user():
    return MagicMock()

@pytest.fixture
def mock_mcp_client():
    return MagicMock()

@pytest.fixture
def mock_permission_service():
    return MagicMock()

@pytest.fixture
def mock_llm_provider():
    return MagicMock()

@pytest.mark.asyncio
async def test_run_revive_turn_grafana_mode(
    mock_db, mock_user, mock_mcp_client, mock_permission_service, mock_llm_provider
):
    orchestrator = ReviveOrchestrator(
        mock_db, mock_user, mock_mcp_client, mock_permission_service, mock_llm_provider
    )
    
    # Mock Mode Detector
    mock_mode_result = ModeDetectionResult(mode="grafana", confidence=0.9, detected_intent="dashboard", suggested_tools=[])
    orchestrator.mode_detector.detect = MagicMock(return_value=mock_mode_result)
    
    # Mock Agent and Registry
    with patch("app.services.revive.orchestrator.EnhancedToolRegistry") as MockRegistry, \
         patch("app.services.revive.orchestrator.NativeToolAgent") as MockAgent:
            
        mock_registry_instance = MockRegistry.return_value
        mock_registry_instance.initialize = AsyncMock()
        
        mock_agent_instance = MockAgent.return_value
        
        # Mock stream as async generator
        async def mock_stream_gen(msg):
            yield "Hello"
        mock_agent_instance.stream = mock_stream_gen
        
        # Execute
        chunks = []
        async for chunk in orchestrator.run_revive_turn("show dashboard", []):
            chunks.append(chunk)
            
        # Verify Mode Detection
        orchestrator.mode_detector.detect.assert_called_once()
        
        # Verify Registry Initialization
        MockRegistry.assert_called_once()
        call_kwargs = MockRegistry.call_args[1]
        assert "revive_grafana" in call_kwargs["modules"]
        assert "revive_aiops" not in call_kwargs["modules"]
        mock_registry_instance.initialize.assert_awaited_once()
        
        # Verify Agent Creation
        MockAgent.assert_called_once()
        agent_init_kwargs = MockAgent.call_args[1]
        assert agent_init_kwargs["initial_messages"][0]["role"] == "system"
        assert "GRAFANA Mode" in agent_init_kwargs["initial_messages"][0]["content"]

        # Verify stream content
        assert "data: " in chunks[0] # Mode event
        assert "Hello" in chunks[1]

@pytest.mark.asyncio
async def test_run_revive_turn_aiops_mode(
    mock_db, mock_user, mock_mcp_client, mock_permission_service, mock_llm_provider
):
    orchestrator = ReviveOrchestrator(
        mock_db, mock_user, mock_mcp_client, mock_permission_service, mock_llm_provider
    )
    
    mock_mode_result = ModeDetectionResult(mode="aiops", confidence=0.9, detected_intent="runbook", suggested_tools=[])
    orchestrator.mode_detector.detect = MagicMock(return_value=mock_mode_result)
    
    with patch("app.services.revive.orchestrator.EnhancedToolRegistry") as MockRegistry, \
         patch("app.services.revive.orchestrator.NativeToolAgent") as MockAgent:
            
        mock_registry_instance = MockRegistry.return_value
        mock_registry_instance.initialize = AsyncMock()
        
        mock_agent_instance = MockAgent.return_value
        mock_agent_instance.stream = lambda msg: (yield "Executing") # Simpler mock if needed, but async generator preferred
        
        async def mock_stream_gen(msg): yield "Executing"
        mock_agent_instance.stream = mock_stream_gen

        async for _ in orchestrator.run_revive_turn("run script", []):
            pass
            
        # Verify Modules
        call_kwargs = MockRegistry.call_args[1]
        assert "revive_aiops" in call_kwargs["modules"]
        assert "revive_grafana" not in call_kwargs["modules"]
        
        # Verify System Prompt
        agent_init_kwargs = MockAgent.call_args[1]
        assert "AIOps Mode" in agent_init_kwargs["initial_messages"][0]["content"]
