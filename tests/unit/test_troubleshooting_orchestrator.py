import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, ANY
from uuid import uuid4

from app.services.agentic.troubleshooting_orchestrator import TroubleshootingOrchestrator
from app.models import User, Alert, LLMProvider

@pytest.fixture
def mock_db_session():
    return MagicMock()

@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = uuid4()
    return user

@pytest.fixture
def mock_alert():
    alert = MagicMock(spec=Alert)
    alert.id = uuid4()
    return alert

@pytest.fixture
def mock_provider():
    return MagicMock(spec=LLMProvider)

@pytest.mark.asyncio
async def test_run_troubleshooting_turn(mock_db_session, mock_user, mock_alert, mock_provider):
    # Mock dependencies
    with patch('app.services.agentic.troubleshooting_orchestrator.TroubleshootingContextEnricher') as MockEnricher, \
         patch('app.services.agentic.troubleshooting_orchestrator.EnhancedToolRegistry') as MockRegistry, \
         patch('app.services.agentic.troubleshooting_orchestrator.NativeToolAgent') as MockAgent:
        
        # Setup Enricher
        enricher_instance = MockEnricher.return_value
        enricher_instance.enrich = AsyncMock(return_value=MagicMock(
            sift_analysis="Analysis", 
            oncall_info="Schedule", 
            similar_incidents=[],
            alert_summary="Summary"
        ))
        
        # Setup Registry
        registry_instance = MockRegistry.return_value
        registry_instance.initialize = AsyncMock()
        
        # Setup Agent
        agent_instance = MockAgent.return_value
        # Mock stream to yield chunks
        async def mock_stream(msg):
            yield "Chunk 1"
            yield "Chunk 2"
        agent_instance.stream = mock_stream
        agent_instance.tool_calls_made = ["tool1"]

        # Instantiate Orchestrator
        orchestrator = TroubleshootingOrchestrator(
            db=mock_db_session,
            user=mock_user,
            alert_id=mock_alert.id,
            mcp_client=MagicMock(),
            permission_service=MagicMock(),
            llm_provider=mock_provider
        )

        # Run turn (empty history -> triggers enrichment)
        chunks = []
        async for chunk in orchestrator.run_troubleshooting_turn("Test message", []):
            chunks.append(chunk)

        # Assertions
        assert chunks == ["Chunk 1", "Chunk 2"]
        assert orchestrator.tool_calls_made == ["tool1"]
        
        # Check Enrichment called
        MockEnricher.assert_called_once()
        enricher_instance.enrich.assert_called_once()
        
        # Check Registry Initialized
        MockRegistry.assert_called_once()
        registry_instance.initialize.assert_called_once()
        
        # Check Agent Initialized with history containing system context
        MockAgent.assert_called_once()
        _, kwargs = MockAgent.call_args
        assert "initial_messages" in kwargs
        # Should have system message + empty history (passed as empty list)
        # Wait, run_troubleshooting_turn calls list(session_messages).
        # And injects system message. So length should be 1 (system msg).
        assert len(kwargs["initial_messages"]) == 1
        assert kwargs["initial_messages"][0]["role"] == "system"
        assert "Context Enriched" in kwargs["initial_messages"][0]["content"]

@pytest.mark.asyncio
async def test_run_troubleshooting_turn_no_enrichment(mock_db_session, mock_user, mock_alert, mock_provider):
    # Test case where history exists, so we don't re-enrich
    with patch('app.services.agentic.troubleshooting_orchestrator.TroubleshootingContextEnricher') as MockEnricher, \
         patch('app.services.agentic.troubleshooting_orchestrator.EnhancedToolRegistry') as MockRegistry, \
         patch('app.services.agentic.troubleshooting_orchestrator.NativeToolAgent') as MockAgent:
        
        # Setup Agent
        agent_instance = MockAgent.return_value
        agent_instance.stream = lambda msg: (async def_gen() for async def_gen in [list(),]).__anext__() # Mock empty stream properly?
        # Simpler:
        async def mock_stream(msg):
            yield "Response"
        agent_instance.stream = mock_stream

        # Setup Registry
        registry_instance = MockRegistry.return_value
        registry_instance.initialize = AsyncMock()

        orchestrator = TroubleshootingOrchestrator(
            db=mock_db_session,
            user=mock_user,
            alert_id=mock_alert.id,
            mcp_client=MagicMock(),
            llm_provider=mock_provider
        )

        existing_history = [{"role": "user", "content": "prev info"}]
        
        # Run turn
        chunks = []
        async for chunk in orchestrator.run_troubleshooting_turn("New message", existing_history):
            chunks.append(chunk)

        assert chunks == ["Response"]
        
        # Verify Enrichment NOT called
        MockEnricher.assert_not_called()
        
        # Verify Agent setup matches existing history
        _, kwargs = MockAgent.call_args
        assert kwargs["initial_messages"] == existing_history # Should match passed list (copy)
