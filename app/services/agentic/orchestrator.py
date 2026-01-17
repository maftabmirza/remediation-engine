"""
Agentic Orchestrator

Routes requests to the appropriate agent based on LLM provider capabilities.
- Native Tool Calling: OpenAI, Anthropic, Google
- ReAct Text Parsing: Ollama, local LLMs
"""

import logging
from typing import Optional, AsyncGenerator, Union
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import LLMProvider, Alert
from app.services.agentic.native_agent import NativeToolAgent, AgentResponse
from app.services.agentic.react_agent import ReActAgent

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator"""
    max_iterations: int = 7
    temperature: float = 0.3
    max_tokens: int = 2000
    enable_streaming: bool = True
    log_tool_calls: bool = True


class AgenticOrchestrator:
    """
    Main orchestrator for the agentic RAG system.

    Automatically routes to the appropriate agent based on provider capabilities:
    - NativeToolAgent for providers with native function calling
    - ReActAgent for providers without native function calling

    Usage:
        orchestrator = AgenticOrchestrator(db, provider, alert)
        response = await orchestrator.run("Why is the CPU high?")

        # Or with streaming:
        async for chunk in orchestrator.stream("Why is the CPU high?"):
            print(chunk, end="")
    """

    # Providers that support native tool calling
    NATIVE_TOOL_PROVIDERS = ["openai", "anthropic", "google"]

    def __init__(
        self,
        db: Session,
        provider: LLMProvider,
        alert: Optional[Alert] = None,
        config: Optional[OrchestratorConfig] = None
    ):
        """
        Initialize the orchestrator.

        Args:
            db: Database session
            provider: LLM provider to use
            alert: Current alert context (optional)
            config: Orchestrator configuration (optional)
        """
        self.db = db
        self.provider = provider
        self.alert = alert
        self.config = config or OrchestratorConfig()

        # Determine which agent to use
        self._agent = self._create_agent()

        logger.info(
            f"AgenticOrchestrator initialized with {type(self._agent).__name__} "
            f"for provider {provider.provider_type}"
        )

    def _create_agent(self) -> Union[NativeToolAgent, ReActAgent]:
        """Create the appropriate agent based on provider type"""
        if self.provider.provider_type in self.NATIVE_TOOL_PROVIDERS:
            return NativeToolAgent(
                db=self.db,
                provider=self.provider,
                alert=self.alert,
                max_iterations=self.config.max_iterations,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
        else:
            return ReActAgent(
                db=self.db,
                provider=self.provider,
                alert=self.alert,
                max_iterations=self.config.max_iterations,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )

    @property
    def agent_type(self) -> str:
        """Get the type of agent being used"""
        return type(self._agent).__name__

    @property
    def uses_native_tools(self) -> bool:
        """Check if using native tool calling"""
        return isinstance(self._agent, NativeToolAgent)

    async def run(self, user_message: str) -> AgentResponse:
        """
        Run the agentic flow with a user message.

        The agent will:
        1. Analyze the user's question
        2. Call tools as needed to gather information
        3. Synthesize findings into a response

        Args:
            user_message: The user's question or request

        Returns:
            AgentResponse with content, tool calls made, and metadata
        """
        logger.info(f"Orchestrator running with message: {user_message[:100]}...")

        response = await self._agent.run(user_message)

        if self.config.log_tool_calls and response.tool_calls_made:
            logger.info(f"Tools called: {response.tool_calls_made}")

        return response

    async def stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """
        Stream the agentic response.

        Yields response chunks including:
        - Tool call notifications
        - Final response content

        Args:
            user_message: The user's question

        Yields:
            Response chunks as strings
        """
        logger.info(f"Orchestrator streaming with message: {user_message[:100]}...")

        async for chunk in self._agent.stream(user_message):
            yield chunk

    def get_tool_calls(self) -> list:
        """Get list of tool calls made in the last run"""
        return getattr(self._agent, 'tool_calls_made', [])

    def clear_history(self):
        """Clear conversation history"""
        if hasattr(self._agent, 'clear_history'):
            self._agent.clear_history()
        elif hasattr(self._agent, 'clear_context'):
            self._agent.clear_context()


# ============= Integration with existing chat service =============





# ============= Utility functions =============


def get_supported_providers() -> dict:
    """
    Get information about supported providers and their capabilities.

    Returns:
        Dict mapping provider types to their capabilities
    """
    return {
        "openai": {
            "agent_type": "NativeToolAgent",
            "supports_tool_calling": True,
            "supports_streaming": True,
            "notes": "Full native function calling support"
        },
        "anthropic": {
            "agent_type": "NativeToolAgent",
            "supports_tool_calling": True,
            "supports_streaming": True,
            "notes": "Full native tool use support"
        },
        "google": {
            "agent_type": "NativeToolAgent",
            "supports_tool_calling": True,
            "supports_streaming": True,
            "notes": "Full native function calling support"
        },
        "ollama": {
            "agent_type": "ReActAgent",
            "supports_tool_calling": False,
            "supports_streaming": True,
            "notes": "Text-based ReAct pattern for tool usage"
        },
        "local": {
            "agent_type": "ReActAgent",
            "supports_tool_calling": False,
            "supports_streaming": True,
            "notes": "Text-based ReAct pattern for tool usage"
        }
    }
