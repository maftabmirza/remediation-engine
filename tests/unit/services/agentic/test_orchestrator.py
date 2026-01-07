"""
Tests for the AgenticOrchestrator component.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from app.services.agentic.orchestrator import (
    AgenticOrchestrator,
    OrchestratorConfig,
    get_supported_providers
)
from app.services.agentic.native_agent import NativeToolAgent
from app.services.agentic.react_agent import ReActAgent


class TestOrchestratorConfig:
    """Tests for OrchestratorConfig dataclass"""

    def test_default_config(self):
        """Test default configuration values"""
        config = OrchestratorConfig()

        assert config.max_iterations == 7
        assert config.temperature == 0.3
        assert config.max_tokens == 2000
        assert config.enable_streaming is True
        assert config.log_tool_calls is True

    def test_custom_config(self):
        """Test custom configuration values"""
        config = OrchestratorConfig(
            max_iterations=5,
            temperature=0.5,
            max_tokens=3000,
            enable_streaming=False,
            log_tool_calls=False
        )

        assert config.max_iterations == 5
        assert config.temperature == 0.5
        assert config.max_tokens == 3000
        assert config.enable_streaming is False
        assert config.log_tool_calls is False


class TestAgenticOrchestrator:
    """Tests for AgenticOrchestrator class"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        return MagicMock()

    @pytest.fixture
    def openai_provider(self):
        """Create a mock OpenAI provider"""
        provider = MagicMock()
        provider.provider_type = "openai"
        provider.model_id = "gpt-4"
        provider.api_key_encrypted = None
        provider.api_base_url = None
        provider.config_json = {"temperature": 0.3, "max_tokens": 2000}
        return provider

    @pytest.fixture
    def anthropic_provider(self):
        """Create a mock Anthropic provider"""
        provider = MagicMock()
        provider.provider_type = "anthropic"
        provider.model_id = "claude-3-sonnet"
        provider.api_key_encrypted = None
        provider.api_base_url = None
        provider.config_json = {"temperature": 0.3, "max_tokens": 2000}
        return provider

    @pytest.fixture
    def ollama_provider(self):
        """Create a mock Ollama provider"""
        provider = MagicMock()
        provider.provider_type = "ollama"
        provider.model_id = "llama2"
        provider.api_base_url = "http://localhost:11434"
        provider.config_json = {"temperature": 0.3, "max_tokens": 2000}
        return provider

    @pytest.fixture
    def mock_alert(self):
        """Create a mock alert"""
        alert = MagicMock()
        alert.id = uuid4()
        alert.alert_name = "HighCPU"
        alert.severity = "critical"
        alert.instance = "api-server-01"
        alert.status = "firing"
        alert.annotations_json = {"summary": "CPU usage high"}
        return alert

    def test_orchestrator_selects_native_agent_for_openai(self, mock_db, openai_provider):
        """Test orchestrator selects NativeToolAgent for OpenAI"""
        orchestrator = AgenticOrchestrator(
            db=mock_db,
            provider=openai_provider
        )

        assert orchestrator.uses_native_tools is True
        assert orchestrator.agent_type == "NativeToolAgent"
        assert isinstance(orchestrator._agent, NativeToolAgent)

    def test_orchestrator_selects_native_agent_for_anthropic(self, mock_db, anthropic_provider):
        """Test orchestrator selects NativeToolAgent for Anthropic"""
        orchestrator = AgenticOrchestrator(
            db=mock_db,
            provider=anthropic_provider
        )

        assert orchestrator.uses_native_tools is True
        assert orchestrator.agent_type == "NativeToolAgent"

    def test_orchestrator_selects_react_agent_for_ollama(self, mock_db, ollama_provider):
        """Test orchestrator selects ReActAgent for Ollama"""
        orchestrator = AgenticOrchestrator(
            db=mock_db,
            provider=ollama_provider
        )

        assert orchestrator.uses_native_tools is False
        assert orchestrator.agent_type == "ReActAgent"
        assert isinstance(orchestrator._agent, ReActAgent)

    def test_orchestrator_with_alert_context(self, mock_db, openai_provider, mock_alert):
        """Test orchestrator passes alert context to agent"""
        orchestrator = AgenticOrchestrator(
            db=mock_db,
            provider=openai_provider,
            alert=mock_alert
        )

        assert orchestrator._agent.alert == mock_alert

    def test_orchestrator_with_custom_config(self, mock_db, openai_provider):
        """Test orchestrator applies custom configuration"""
        config = OrchestratorConfig(
            max_iterations=3,
            temperature=0.5
        )

        orchestrator = AgenticOrchestrator(
            db=mock_db,
            provider=openai_provider,
            config=config
        )

        assert orchestrator._agent.max_iterations == 3
        assert orchestrator._agent.temperature == 0.5

    def test_get_tool_calls(self, mock_db, openai_provider):
        """Test getting tool calls from orchestrator"""
        orchestrator = AgenticOrchestrator(
            db=mock_db,
            provider=openai_provider
        )

        # Simulate tool calls
        orchestrator._agent.tool_calls_made = ["search_knowledge", "get_runbook"]

        tool_calls = orchestrator.get_tool_calls()
        assert tool_calls == ["search_knowledge", "get_runbook"]

    def test_clear_history(self, mock_db, openai_provider):
        """Test clearing history through orchestrator"""
        orchestrator = AgenticOrchestrator(
            db=mock_db,
            provider=openai_provider
        )

        # Add some history
        orchestrator._agent.messages = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "hello"}
        ]

        orchestrator.clear_history()

        # Should have only system message
        assert len(orchestrator._agent.messages) == 1

    @pytest.mark.asyncio
    async def test_run_delegates_to_agent(self, mock_db, openai_provider):
        """Test run method delegates to underlying agent"""
        orchestrator = AgenticOrchestrator(
            db=mock_db,
            provider=openai_provider
        )

        mock_response = MagicMock()
        mock_response.content = "Test response"
        mock_response.tool_calls_made = []
        mock_response.iterations = 1
        mock_response.finished = True

        with patch.object(orchestrator._agent, 'run', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_response

            response = await orchestrator.run("Test question")

            mock_run.assert_called_once_with("Test question")
            assert response.content == "Test response"

    @pytest.mark.asyncio
    async def test_stream_delegates_to_agent(self, mock_db, openai_provider):
        """Test stream method delegates to underlying agent"""
        orchestrator = AgenticOrchestrator(
            db=mock_db,
            provider=openai_provider
        )

        async def mock_stream(message):
            yield "chunk1"
            yield "chunk2"

        with patch.object(orchestrator._agent, 'stream', side_effect=mock_stream):
            chunks = []
            async for chunk in orchestrator.stream("Test question"):
                chunks.append(chunk)

            assert chunks == ["chunk1", "chunk2"]


class TestGetSupportedProviders:
    """Tests for get_supported_providers utility function"""

    def test_returns_all_providers(self):
        """Test that all provider info is returned"""
        providers = get_supported_providers()

        assert "openai" in providers
        assert "anthropic" in providers
        assert "google" in providers
        assert "ollama" in providers
        assert "local" in providers

    def test_openai_capabilities(self):
        """Test OpenAI provider capabilities"""
        providers = get_supported_providers()
        openai = providers["openai"]

        assert openai["agent_type"] == "NativeToolAgent"
        assert openai["supports_tool_calling"] is True
        assert openai["supports_streaming"] is True

    def test_ollama_capabilities(self):
        """Test Ollama provider capabilities"""
        providers = get_supported_providers()
        ollama = providers["ollama"]

        assert ollama["agent_type"] == "ReActAgent"
        assert ollama["supports_tool_calling"] is False
        assert ollama["supports_streaming"] is True


class TestOrchestratorIntegration:
    """Integration tests for orchestrator with mocked services"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def openai_provider(self):
        provider = MagicMock()
        provider.provider_type = "openai"
        provider.model_id = "gpt-4"
        provider.api_key_encrypted = None
        provider.api_base_url = None
        provider.config_json = {"temperature": 0.3, "max_tokens": 2000}
        return provider

    @pytest.mark.asyncio
    async def test_full_run_with_tool_calls(self, mock_db, openai_provider):
        """Test full orchestrator run with tool calls"""
        orchestrator = AgenticOrchestrator(
            db=mock_db,
            provider=openai_provider
        )

        # Mock the LLM to return tool calls then final response
        call_count = [0]

        async def mock_call_llm():
            call_count[0] += 1
            response = MagicMock()
            message = MagicMock()

            if call_count[0] == 1:
                # First call: return tool call
                tool_call = MagicMock()
                tool_call.id = "call_1"
                tool_call.function.name = "search_knowledge"
                tool_call.function.arguments = '{"query": "test"}'
                message.content = ""
                message.tool_calls = [tool_call]
            else:
                # Second call: final response
                message.content = "Based on the search results..."
                message.tool_calls = None

            response.choices = [MagicMock(message=message)]
            return response

        with patch.object(orchestrator._agent, '_call_llm', side_effect=mock_call_llm):
            with patch.object(orchestrator._agent.tool_registry, 'execute', new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = "Search results..."

                response = await orchestrator.run("What is the issue?")

                assert response.finished is True
                assert "search_knowledge" in response.tool_calls_made
                assert response.iterations == 2
