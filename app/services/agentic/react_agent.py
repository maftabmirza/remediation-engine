"""
ReAct (Reasoning + Acting) Agent

Text-based agent for LLMs that don't support native tool calling.
Uses the ReAct prompting pattern to parse tool calls from text output.

Works with Ollama and other local LLMs.
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional, AsyncGenerator
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import LLMProvider, Alert
from app.services.ollama_service import ollama_completion
from app.services.agentic.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentResponse:
    """Response from the agent"""
    content: str
    tool_calls_made: List[str]
    iterations: int
    finished: bool
    error: Optional[str] = None


class ReActAgent:
    """
    ReAct agent using text-based tool calling.

    Parses "Action:" and "Action Input:" patterns from LLM output
    to execute tools, then injects "Observation:" with results.

    Works with any LLM including Ollama and local models.
    """

    # Pattern to extract action and action input
    ACTION_PATTERN = re.compile(
        r"Action:\s*(\w+)\s*"
        r"Action Input:\s*(\{.*?\}|\S+)",
        re.DOTALL | re.IGNORECASE
    )

    # Pattern to detect final answer
    FINAL_ANSWER_PATTERN = re.compile(
        r"Final Answer:\s*(.*)",
        re.DOTALL | re.IGNORECASE
    )

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
        Initialize the ReAct agent.

        Args:
            db: Database session
            provider: LLM provider to use
            alert: Current alert context (optional)
            max_iterations: Maximum reasoning iterations
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

        # Conversation context
        self.context = ""
        self.tool_calls_made: List[str] = []

    def _get_system_prompt(self) -> str:
        """Generate the ReAct system prompt with tool descriptions"""
        tools_desc = self.tool_registry.get_react_tools_description()

        base_prompt = f"""You are Antigravity, an advanced SRE AI Agent.
You are pair-programming with the user to investigate and resolve production incidents.

You have access to the following tools:

{tools_desc}

## How to Use Tools:

When you need information, use this EXACT format:

Thought: [Your reasoning about what information you need]
Action: [tool_name]
Action Input: {{"param": "value"}}

After each action, you will receive an Observation with the tool's output.
Continue this process until you have enough information to answer.

When you're ready to provide your final response, use:

Thought: I now have enough information to answer
Final Answer: [Your complete response to the user]

## Guidelines:
- Always start with a Thought explaining your reasoning
- Use tools to gather information before making recommendations
- Be specific with tool parameters
- After gathering information, provide actionable recommendations
- Keep the Final Answer concise but complete

## Format for Final Answer:
1. Summary of what you found
2. Diagnosis/hypothesis
3. Specific remediation steps with commands if applicable
"""

        # Add alert context if available
        if self.alert:
            alert_context = f"""
## Current Alert Context:
- Name: {self.alert.alert_name}
- Severity: {self.alert.severity}
- Instance: {self.alert.instance}
- Status: {self.alert.status}
- Summary: {(self.alert.annotations_json or {}).get('summary', 'N/A')}
"""
            base_prompt += alert_context

        return base_prompt

    def _parse_action(self, response: str) -> Optional[tuple]:
        """
        Parse action and action input from response.

        Returns:
            Tuple of (action_name, arguments_dict) or None if no action found
        """
        # Look for Action pattern
        match = self.ACTION_PATTERN.search(response)
        if not match:
            return None

        action_name = match.group(1).strip()
        action_input_raw = match.group(2).strip()

        # Parse arguments
        try:
            # Try JSON parsing first
            if action_input_raw.startswith('{'):
                arguments = json.loads(action_input_raw)
            else:
                # Single value - assume it's the first required parameter
                arguments = {"query": action_input_raw}
        except json.JSONDecodeError:
            # Fallback - treat as string query
            arguments = {"query": action_input_raw}

        return (action_name, arguments)

    def _parse_final_answer(self, response: str) -> Optional[str]:
        """
        Parse final answer from response.

        Returns:
            Final answer string or None if not found
        """
        match = self.FINAL_ANSWER_PATTERN.search(response)
        if match:
            return match.group(1).strip()
        return None

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM with the current context"""
        if self.provider.provider_type == "ollama":
            # Use Ollama service
            messages = [{"role": "user", "content": prompt}]
            response = await ollama_completion(
                provider=self.provider,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            return response
        else:
            # Use LiteLLM for other providers
            from litellm import acompletion
            from app.services.llm_service import get_api_key_for_provider

            api_key = get_api_key_for_provider(self.provider)

            kwargs = {
                "model": self.provider.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }

            if api_key:
                kwargs["api_key"] = api_key

            if self.provider.api_base_url:
                kwargs["api_base"] = self.provider.api_base_url

            response = await acompletion(**kwargs)
            return response.choices[0].message.content or ""

    async def run(self, user_message: str) -> AgentResponse:
        """
        Run the agent with a user message.

        Args:
            user_message: The user's question or request

        Returns:
            AgentResponse with the final response and metadata
        """
        # Build initial prompt
        system_prompt = self._get_system_prompt()
        self.context = f"{system_prompt}\n\nUser Question: {user_message}\n\n"

        iterations = 0
        self.tool_calls_made = []

        try:
            while iterations < self.max_iterations:
                iterations += 1
                logger.info(f"ReAct iteration {iterations}")

                # Add instruction to continue
                if iterations == 1:
                    prompt = self.context + "Begin your investigation. Remember to use the Thought/Action/Action Input format.\n\nThought:"
                else:
                    prompt = self.context + "\nThought:"

                # Call LLM
                response = await self._call_llm(prompt)

                # Add response to context
                self.context += f"Thought:{response}\n"

                # Check for final answer
                final_answer = self._parse_final_answer(response)
                if final_answer:
                    return AgentResponse(
                        content=final_answer,
                        tool_calls_made=self.tool_calls_made,
                        iterations=iterations,
                        finished=True
                    )

                # Check for action
                action = self._parse_action(response)
                if action:
                    action_name, arguments = action
                    logger.info(f"ReAct executing tool: {action_name} with args: {arguments}")
                    self.tool_calls_made.append(action_name)

                    # Execute tool
                    result = await self.tool_registry.execute(action_name, arguments)

                    # Add observation to context
                    self.context += f"\nObservation: {result}\n"

                    # Continue to next iteration
                    continue

                # No action and no final answer - prompt for continuation
                # Check if response seems complete (heuristic)
                if "recommend" in response.lower() or "suggest" in response.lower():
                    # Treat as implicit final answer
                    return AgentResponse(
                        content=response,
                        tool_calls_made=self.tool_calls_made,
                        iterations=iterations,
                        finished=True
                    )

                # Ask for continuation
                self.context += "\n(Continue with either an Action or Final Answer)\n"

            # Max iterations reached
            logger.warning(f"ReAct agent reached max iterations ({self.max_iterations})")

            # Try to extract useful content from context
            # Look for the last substantial response
            return AgentResponse(
                content="Based on my investigation, I've gathered the following information. Let me summarize what I found in the observations above.",
                tool_calls_made=self.tool_calls_made,
                iterations=iterations,
                finished=False,
                error="Max iterations reached"
            )

        except Exception as e:
            logger.error(f"ReAct agent error: {e}")
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

        Yields status updates and the final response.

        Args:
            user_message: The user's question

        Yields:
            Response chunks as strings
        """
        # Build initial prompt
        system_prompt = self._get_system_prompt()
        self.context = f"{system_prompt}\n\nUser Question: {user_message}\n\n"

        iterations = 0
        self.tool_calls_made = []

        try:
            while iterations < self.max_iterations:
                iterations += 1

                # Add instruction to continue
                if iterations == 1:
                    prompt = self.context + "Begin your investigation. Remember to use the Thought/Action/Action Input format.\n\nThought:"
                else:
                    prompt = self.context + "\nThought:"

                # Call LLM
                response = await self._call_llm(prompt)

                # Add response to context
                self.context += f"Thought:{response}\n"

                # Check for final answer
                final_answer = self._parse_final_answer(response)
                if final_answer:
                    yield final_answer
                    return

                # Check for action
                action = self._parse_action(response)
                if action:
                    action_name, arguments = action
                    self.tool_calls_made.append(action_name)

                    # Notify about tool call
                    yield f"\n🔍 *Calling tool: {action_name}...*\n"

                    # Execute tool
                    result = await self.tool_registry.execute(action_name, arguments)

                    # Add observation to context
                    self.context += f"\nObservation: {result}\n"

                    continue

                # No action and no final answer
                if "recommend" in response.lower() or "suggest" in response.lower():
                    yield response
                    return

                self.context += "\n(Continue with either an Action or Final Answer)\n"

            # Max iterations
            yield "\n\n*[Max iterations reached - summarizing findings]*"

        except Exception as e:
            logger.error(f"ReAct stream error: {e}")
            yield f"\n\n*Error: {str(e)}*"

    def get_full_context(self) -> str:
        """Get the full reasoning context (for debugging)"""
        return self.context

    def clear_context(self):
        """Clear the conversation context"""
        self.context = ""
        self.tool_calls_made = []
