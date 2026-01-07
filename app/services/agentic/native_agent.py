"""
Native Tool Calling Agent

Uses native function/tool calling capabilities of LLM providers
(OpenAI, Anthropic, Google) for reliable structured tool invocation.
"""

import json
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session
from litellm import acompletion

from app.models import LLMProvider, Alert
from app.services.llm_service import get_api_key_for_provider
from app.services.agentic.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    """A message in the agent conversation"""
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # Tool name for tool messages


@dataclass
class AgentResponse:
    """Response from the agent"""
    content: str
    tool_calls_made: List[str]
    iterations: int
    finished: bool
    error: Optional[str] = None


class NativeToolAgent:
    """
    Agent that uses native tool calling capabilities.

    Works with OpenAI, Anthropic, and Google providers via LiteLLM.
    """

    # Providers that support native tool calling
    SUPPORTED_PROVIDERS = ["openai", "anthropic", "google"]

    def __init__(
        self,
        db: Session,
        provider: LLMProvider,
        alert: Optional[Alert] = None,
        max_iterations: int = 7,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ):
        """
        Initialize the native tool agent.

        Args:
            db: Database session
            provider: LLM provider to use
            alert: Current alert context (optional)
            max_iterations: Maximum tool call iterations
            temperature: LLM temperature
            max_tokens: Max tokens per response
        """
        self.db = db
        self.provider = provider
        self.alert = alert
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Initialize tool registry
        alert_id = alert.id if alert else None
        self.tool_registry = ToolRegistry(db, alert_id=alert_id)

        # Conversation history
        self.messages: List[Dict[str, Any]] = []
        self.tool_calls_made: List[str] = []

    @classmethod
    def supports_provider(cls, provider_type: str) -> bool:
        """Check if this agent supports the given provider type"""
        return provider_type in cls.SUPPORTED_PROVIDERS

    def _get_system_prompt(self) -> str:
        """Generate the system prompt for the agent"""
        base_prompt = """You are Antigravity, an advanced SRE AI Agent.
You are pair-programming with the user to investigate and resolve production incidents.

## Your Operating Mode:
1. **Tool-First Approach**: You have access to tools to gather information. Use them to investigate before making recommendations.
2. **Iterative Troubleshooting**: Gather information step by step. Don't ask for everything at once.
3. **Evidence-Based**: Always cite which tools informed your conclusions.
4. **Actionable**: When you have enough information, provide specific commands or actions.

## Available Tools:
You can call tools to:
- Search the knowledge base for runbooks and SOPs
- Find similar past incidents and their resolutions
- Check recent changes/deployments
- Query metrics and logs from Grafana
- Get correlated alerts and root cause analysis
- Find service dependencies

## Guidelines:
- Start by understanding what information you need
- Call tools as needed - you don't need to call all of them
- After gathering information, synthesize and provide actionable recommendations
- Keep responses concise and focused
- Use **bold** for key concepts and `code blocks` for commands

## Format:
When you have enough information to respond:
1. Summarize what you found
2. Provide your hypothesis/diagnosis
3. Give specific remediation steps with commands if applicable
"""
        # Add alert context if available
        if self.alert:
            alert_context = f"""
## Current Alert Context:
- **Name:** {self.alert.alert_name}
- **Severity:** {self.alert.severity}
- **Instance:** {self.alert.instance}
- **Status:** {self.alert.status}
- **Summary:** {(self.alert.annotations_json or {}).get('summary', 'N/A')}
"""
            base_prompt += alert_context

        return base_prompt

    def _get_tools_for_provider(self) -> List[Dict[str, Any]]:
        """Get tools in the format expected by the provider"""
        if self.provider.provider_type == "anthropic":
            return self.tool_registry.get_anthropic_tools()
        else:
            # OpenAI and Google use the same format
            return self.tool_registry.get_openai_tools()

    async def _call_llm(self) -> Dict[str, Any]:
        """Call the LLM with current messages and tools"""
        api_key = get_api_key_for_provider(self.provider)

        kwargs = {
            "model": self.provider.model_id,
            "messages": self.messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "tools": self._get_tools_for_provider(),
        }

        if api_key:
            kwargs["api_key"] = api_key

        if self.provider.api_base_url:
            kwargs["api_base"] = self.provider.api_base_url

        response = await acompletion(**kwargs)
        return response

    async def _execute_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """Execute tool calls and return results"""
        results = []

        for tool_call in tool_calls:
            # Extract tool info (handle different provider formats)
            if hasattr(tool_call, 'function'):
                # OpenAI format
                tool_name = tool_call.function.name
                tool_id = tool_call.id
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}
            elif hasattr(tool_call, 'name'):
                # Anthropic format
                tool_name = tool_call.name
                tool_id = tool_call.id if hasattr(tool_call, 'id') else tool_name
                arguments = tool_call.input if hasattr(tool_call, 'input') else {}
            else:
                # Dict format (fallback)
                tool_name = tool_call.get('function', {}).get('name', tool_call.get('name', ''))
                tool_id = tool_call.get('id', tool_name)
                arguments = tool_call.get('function', {}).get('arguments', tool_call.get('input', {}))
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

            logger.info(f"Executing tool: {tool_name} with args: {arguments}")
            self.tool_calls_made.append(tool_name)

            # Execute the tool
            result = await self.tool_registry.execute(tool_name, arguments)

            results.append({
                "tool_call_id": tool_id,
                "role": "tool",
                "name": tool_name,
                "content": result
            })

        return results

    async def run(self, user_message: str) -> AgentResponse:
        """
        Run the agent with a user message.

        Args:
            user_message: The user's question or request

        Returns:
            AgentResponse with the final response and metadata
        """
        # Initialize conversation if empty
        if not self.messages:
            self.messages.append({
                "role": "system",
                "content": self._get_system_prompt()
            })

        # Add user message
        self.messages.append({
            "role": "user",
            "content": user_message
        })

        iterations = 0
        self.tool_calls_made = []

        try:
            while iterations < self.max_iterations:
                iterations += 1
                logger.info(f"Agent iteration {iterations}")

                # Call LLM
                response = await self._call_llm()
                message = response.choices[0].message

                # Check for tool calls
                tool_calls = getattr(message, 'tool_calls', None)

                if tool_calls:
                    # Add assistant message with tool calls
                    self.messages.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in tool_calls
                        ]
                    })

                    # Execute tools
                    tool_results = await self._execute_tool_calls(tool_calls)

                    # Add tool results to messages
                    for result in tool_results:
                        self.messages.append(result)

                    # Continue loop for next iteration
                    continue

                else:
                    # No tool calls - final response
                    final_content = message.content or ""

                    # Add to messages
                    self.messages.append({
                        "role": "assistant",
                        "content": final_content
                    })

                    return AgentResponse(
                        content=final_content,
                        tool_calls_made=self.tool_calls_made,
                        iterations=iterations,
                        finished=True
                    )

            # Max iterations reached
            logger.warning(f"Agent reached max iterations ({self.max_iterations})")
            return AgentResponse(
                content="I've gathered a lot of information but need to stop here. Based on what I've found, let me summarize...",
                tool_calls_made=self.tool_calls_made,
                iterations=iterations,
                finished=False,
                error="Max iterations reached"
            )

        except Exception as e:
            logger.error(f"Agent error: {e}")
            return AgentResponse(
                content=f"I encountered an error during investigation: {str(e)}",
                tool_calls_made=self.tool_calls_made,
                iterations=iterations,
                finished=False,
                error=str(e)
            )

    async def stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """
        Stream the agent response.

        For tool-calling agents, this yields:
        - Tool call notifications as they happen
        - The final response content

        Args:
            user_message: The user's question

        Yields:
            Response chunks as strings
        """
        # Initialize conversation if empty
        if not self.messages:
            self.messages.append({
                "role": "system",
                "content": self._get_system_prompt()
            })

        # Add user message
        self.messages.append({
            "role": "user",
            "content": user_message
        })

        iterations = 0
        self.tool_calls_made = []

        try:
            while iterations < self.max_iterations:
                iterations += 1

                # Call LLM (non-streaming for tool detection)
                response = await self._call_llm()
                message = response.choices[0].message

                tool_calls = getattr(message, 'tool_calls', None)

                if tool_calls:
                    # Notify about tool calls
                    for tc in tool_calls:
                        tool_name = tc.function.name if hasattr(tc, 'function') else tc.get('name', 'unknown')
                        yield f"\n🔍 *Calling tool: {tool_name}...*\n"

                    # Add assistant message with tool calls
                    self.messages.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in tool_calls
                        ]
                    })

                    # Execute tools
                    tool_results = await self._execute_tool_calls(tool_calls)

                    # Add tool results to messages
                    for result in tool_results:
                        self.messages.append(result)

                    continue

                else:
                    # Final response - yield content
                    final_content = message.content or ""

                    # Add to messages
                    self.messages.append({
                        "role": "assistant",
                        "content": final_content
                    })

                    # Stream the content (simulate streaming for consistency)
                    # In production, you could use actual streaming here
                    yield final_content
                    return

            # Max iterations
            yield "\n\n*[Max tool iterations reached]*"

        except Exception as e:
            logger.error(f"Agent stream error: {e}")
            yield f"\n\n*Error: {str(e)}*"

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the full conversation history"""
        return self.messages.copy()

    def clear_history(self):
        """Clear conversation history (keeps system prompt)"""
        system_prompt = self.messages[0] if self.messages else None
        self.messages = []
        if system_prompt and system_prompt.get("role") == "system":
            self.messages.append(system_prompt)
        self.tool_calls_made = []
