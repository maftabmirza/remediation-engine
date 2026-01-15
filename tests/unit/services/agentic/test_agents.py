"""
Tests for the NativeToolAgent and ReActAgent components.
"""
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from app.services.agentic.native_agent import NativeToolAgent, AgentResponse
from app.services.agentic.react_agent import ReActAgent


class TestNativeToolAgent:
    """Tests for NativeToolAgent class"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        return MagicMock()

    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider"""
        provider = MagicMock()
        provider.provider_type = "openai"
        provider.model_id = "gpt-4"
        provider.api_key_encrypted = None
        provider.api_base_url = None
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
        alert.annotations_json = {"summary": "CPU usage is above 90%"}
        return alert

    def test_supports_openai_provider(self):
        """Test that OpenAI provider is supported"""
        assert NativeToolAgent.supports_provider("openai") is True

    def test_supports_anthropic_provider(self):
        """Test that Anthropic provider is supported"""
        assert NativeToolAgent.supports_provider("anthropic") is True

    def test_supports_google_provider(self):
        """Test that Google provider is supported"""
        assert NativeToolAgent.supports_provider("google") is True

    def test_does_not_support_ollama(self):
        """Test that Ollama is not supported by native agent"""
        assert NativeToolAgent.supports_provider("ollama") is False

    def test_agent_initialization(self, mock_db, mock_provider):
        """Test agent initialization"""
        agent = NativeToolAgent(
            db=mock_db,
            provider=mock_provider
        )

        assert agent.provider == mock_provider
        assert agent.max_iterations == 7
        assert agent.temperature == 0.3
        assert agent.messages == []

    def test_agent_with_alert_context(self, mock_db, mock_provider, mock_alert):
        """Test agent initialization with alert context"""
        agent = NativeToolAgent(
            db=mock_db,
            provider=mock_provider,
            alert=mock_alert
        )

        assert agent.alert == mock_alert
        assert agent.tool_registry.alert_id == mock_alert.id

    def test_get_system_prompt_without_alert(self, mock_db, mock_provider):
        """Test system prompt generation without alert"""
        agent = NativeToolAgent(db=mock_db, provider=mock_provider)
        prompt = agent._get_system_prompt()

        assert "Antigravity" in prompt
        assert "SRE AI Agent" in prompt
        assert "Tool-First Approach" in prompt
        assert "Current Alert Context" not in prompt

    def test_get_system_prompt_with_alert(self, mock_db, mock_provider, mock_alert):
        """Test system prompt generation with alert"""
        agent = NativeToolAgent(db=mock_db, provider=mock_provider, alert=mock_alert)
        prompt = agent._get_system_prompt()

        assert "Current Alert Context" in prompt
        assert "HighCPU" in prompt
        assert "critical" in prompt
        assert "api-server-01" in prompt

    def test_get_tools_for_openai_provider(self, mock_db, mock_provider):
        """Test getting tools in OpenAI format"""
        agent = NativeToolAgent(db=mock_db, provider=mock_provider)
        tools = agent._get_tools_for_provider()

        assert len(tools) >= 10
        for tool in tools:
            assert tool["type"] == "function"

    def test_get_tools_for_anthropic_provider(self, mock_db, mock_provider):
        """Test getting tools in Anthropic format"""
        mock_provider.provider_type = "anthropic"
        agent = NativeToolAgent(db=mock_db, provider=mock_provider)
        tools = agent._get_tools_for_provider()

        assert len(tools) >= 10
        for tool in tools:
            assert "name" in tool
            assert "input_schema" in tool

    def test_clear_history(self, mock_db, mock_provider):
        """Test clearing conversation history"""
        agent = NativeToolAgent(db=mock_db, provider=mock_provider)

        # Add some messages
        agent.messages = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"}
        ]
        agent.tool_calls_made = ["search_knowledge"]

        agent.clear_history()

        # Should keep system prompt
        assert len(agent.messages) == 1
        assert agent.messages[0]["role"] == "system"
        assert agent.tool_calls_made == []

    def test_get_conversation_history(self, mock_db, mock_provider):
        """Test getting conversation history"""
        agent = NativeToolAgent(db=mock_db, provider=mock_provider)
        agent.messages = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "hello"}
        ]

        history = agent.get_conversation_history()

        assert len(history) == 2
        # Should be a copy
        history.append({"role": "test", "content": "test"})
        assert len(agent.messages) == 2

    @pytest.mark.asyncio
    async def test_run_final_response(self, mock_db, mock_provider):
        """Test agent run with immediate final response (no tool calls)"""
        agent = NativeToolAgent(db=mock_db, provider=mock_provider)

        # Mock LLM response without tool calls
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Based on my analysis, the CPU is high due to..."
        mock_message.tool_calls = None
        mock_response.choices = [MagicMock(message=mock_message)]

        with patch.object(agent, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            response = await agent.run("Why is CPU high?")

            assert isinstance(response, AgentResponse)
            assert response.finished is True
            assert "CPU is high" in response.content
            assert response.tool_calls_made == []
            assert response.iterations == 1

    @pytest.mark.asyncio
    async def test_run_max_iterations(self, mock_db, mock_provider):
        """Test agent respects max iterations"""
        agent = NativeToolAgent(db=mock_db, provider=mock_provider, max_iterations=2)

        # Mock LLM always returning tool calls
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = ""
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "search_knowledge"
        mock_tool_call.function.arguments = '{"query": "test"}'
        mock_message.tool_calls = [mock_tool_call]
        mock_response.choices = [MagicMock(message=mock_message)]

        with patch.object(agent, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            with patch.object(agent.tool_registry, 'execute', new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = "Tool result"

                response = await agent.run("Test question")

                assert response.iterations == 2
                assert response.finished is False
                assert "Max iterations reached" in response.error


class TestReActAgent:
    """Tests for ReActAgent class"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        return MagicMock()

    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider for Ollama"""
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
        alert.alert_name = "HighMemory"
        alert.severity = "warning"
        alert.instance = "db-server-01"
        alert.status = "firing"
        alert.annotations_json = {"summary": "Memory usage is above 80%"}
        return alert

    def test_agent_initialization(self, mock_db, mock_provider):
        """Test ReAct agent initialization"""
        agent = ReActAgent(
            db=mock_db,
            provider=mock_provider
        )

        assert agent.provider == mock_provider
        assert agent.max_iterations == 7
        assert agent.context == ""

    def test_get_system_prompt_includes_tools(self, mock_db, mock_provider):
        """Test system prompt includes tool descriptions"""
        agent = ReActAgent(db=mock_db, provider=mock_provider)
        prompt = agent._get_system_prompt()

        assert "search_knowledge" in prompt
        assert "get_similar_incidents" in prompt
        assert "Action:" in prompt
        assert "Action Input:" in prompt
        assert "Final Answer:" in prompt

    def test_get_system_prompt_with_alert(self, mock_db, mock_provider, mock_alert):
        """Test system prompt includes alert context"""
        agent = ReActAgent(db=mock_db, provider=mock_provider, alert=mock_alert)
        prompt = agent._get_system_prompt()

        assert "HighMemory" in prompt
        assert "warning" in prompt
        assert "db-server-01" in prompt

    def test_parse_action_valid(self, mock_db, mock_provider):
        """Test parsing valid action from response"""
        agent = ReActAgent(db=mock_db, provider=mock_provider)

        response = '''
        I need to search for information about this issue.
        Action: search_knowledge
        Action Input: {"query": "high memory usage"}
        '''

        result = agent._parse_action(response)

        assert result is not None
        action_name, arguments = result
        assert action_name == "search_knowledge"
        assert arguments["query"] == "high memory usage"

    def test_parse_action_no_action(self, mock_db, mock_provider):
        """Test parsing response without action"""
        agent = ReActAgent(db=mock_db, provider=mock_provider)

        response = "I think the issue is caused by a memory leak."

        result = agent._parse_action(response)
        assert result is None

    def test_parse_action_simple_input(self, mock_db, mock_provider):
        """Test parsing action with simple string input"""
        agent = ReActAgent(db=mock_db, provider=mock_provider)

        response = '''
        Action: search_knowledge
        Action Input: memory leak troubleshooting
        '''

        result = agent._parse_action(response)

        assert result is not None
        action_name, arguments = result
        assert action_name == "search_knowledge"
        assert "query" in arguments

    def test_parse_final_answer_valid(self, mock_db, mock_provider):
        """Test parsing valid final answer"""
        agent = ReActAgent(db=mock_db, provider=mock_provider)

        response = '''
        Based on my investigation, here is my conclusion.
        Final Answer: The memory issue is caused by a leak in the cache module.
        You should restart the service.
        '''

        result = agent._parse_final_answer(response)

        assert result is not None
        assert "memory issue" in result
        assert "cache module" in result

    def test_parse_final_answer_not_found(self, mock_db, mock_provider):
        """Test parsing response without final answer"""
        agent = ReActAgent(db=mock_db, provider=mock_provider)

        response = "I need to gather more information."

        result = agent._parse_final_answer(response)
        assert result is None

    def test_clear_context(self, mock_db, mock_provider):
        """Test clearing conversation context"""
        agent = ReActAgent(db=mock_db, provider=mock_provider)
        agent.context = "Some previous context"
        agent.tool_calls_made = ["search_knowledge"]

        agent.clear_context()

        assert agent.context == ""
        assert agent.tool_calls_made == []

    def test_get_full_context(self, mock_db, mock_provider):
        """Test getting full reasoning context"""
        agent = ReActAgent(db=mock_db, provider=mock_provider)
        agent.context = "Test context"

        assert agent.get_full_context() == "Test context"

    @pytest.mark.asyncio
    async def test_run_with_final_answer(self, mock_db, mock_provider):
        """Test agent run with immediate final answer"""
        agent = ReActAgent(db=mock_db, provider=mock_provider)

        with patch.object(agent, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = '''
            I can answer this directly.
            Final Answer: The memory is high because of process X.
            '''

            response = await agent.run("Why is memory high?")

            assert response.finished is True
            assert "memory is high" in response.content
            assert response.tool_calls_made == []

    @pytest.mark.asyncio
    async def test_run_with_tool_call(self, mock_db, mock_provider):
        """Test agent run with tool call"""
        agent = ReActAgent(db=mock_db, provider=mock_provider)

        call_count = [0]

        async def mock_llm(prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                return '''
                I need to search for information.
                Action: search_knowledge
                Action Input: {"query": "memory usage"}
                '''
            else:
                return '''
                Based on the search results, I now know the answer.
                Final Answer: The memory is high due to cache growth.
                '''

        with patch.object(agent, '_call_llm', side_effect=mock_llm):
            with patch.object(agent.tool_registry, 'execute', new_callable=AsyncMock) as mock_execute:
                mock_execute.return_value = "Found: Memory management docs"

                response = await agent.run("Why is memory high?")

                assert response.finished is True
                assert "search_knowledge" in response.tool_calls_made
                assert response.iterations == 2


class TestAgentResponse:
    """Tests for AgentResponse dataclass"""

    def test_create_successful_response(self):
        """Test creating a successful response"""
        response = AgentResponse(
            content="The issue is resolved.",
            tool_calls_made=["search_knowledge", "get_runbook"],
            iterations=3,
            finished=True
        )

        assert response.content == "The issue is resolved."
        assert len(response.tool_calls_made) == 2
        assert response.iterations == 3
        assert response.finished is True
        assert response.error is None

    def test_create_error_response(self):
        """Test creating an error response"""
        response = AgentResponse(
            content="An error occurred.",
            tool_calls_made=["search_knowledge"],
            iterations=1,
            finished=False,
            error="Max iterations reached"
        )

        assert response.finished is False
        assert response.error == "Max iterations reached"
