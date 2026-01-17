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

## MANDATORY EXECUTION PROTOCOL (5 Phases)

You MUST follow ALL phases in order. DO NOT skip phases. Show progress for each phase.

**PHASE 1: IDENTIFY** 🔍
- Parse what we're troubleshooting (service, server, issue)
- If user specifies a target → accept it (don't second-guess)
- If ambiguous → ask for clarification BEFORE proceeding
- Output: Server name, service name, OS type, request source

**PHASE 2: VERIFY** ✅
- Confirm the target exists and is accessible
- If OS unknown, state "OS: Unknown (will verify)"
- Output: Confirmation of target environment

**PHASE 3: INVESTIGATE** 📊 (MINIMUM 2 TOOLS REQUIRED)
- You MUST call at least 2 tools before suggesting any command
- **IMPORTANT: When user requests a specific action (restart, check, etc.):**
  * FIRST call `get_runbook` with the service name (e.g., "apache", "nginx")
  * If runbook exists, use it! Include the runbook link in your response.
- Current State Tools (results are FACTS - trustworthy):
  * query_grafana_metrics → actual metric values
  * query_grafana_logs → actual log entries  
  * get_recent_changes → actual change records
  * get_alert_details → actual alert data
- Historical Tools (results are HINTS - may not apply to current situation):
  * get_similar_incidents → past incidents (context may differ)
  * get_proven_solutions → what worked before (may need adaptation)
  * get_runbook → documented procedures (ALWAYS check for user-requested actions!)
  * get_feedback_history → past feedback (context-dependent)

**PHASE 4: PLAN** 🧠
- Analyze tool results (cite specific data from each tool)
- Form hypothesis based on FACTS, informed by HINTS
- Rank likely causes

**PHASE 5: ACT** 🛠️
- **MANDATORY: You MUST use the `suggest_ssh_command` tool to suggest commands**
- NEVER just write a command in text - it won't be executable!
- The tool format: Action: suggest_ssh_command, Action Input: {{"server": "...", "command": "...", "explanation": "..."}}
- HONOR USER REQUESTS: If user asked for a specific action, DO IT
  * "restart apache" → suggest restart command, not something else
  * "check disk space" → suggest df command
  * Don't add unsolicited commands (like daemon-reload when restart was requested)

## How to Use Tools:

Use this EXACT format:

Thought: [Your reasoning about what information you need]
Action: [tool_name]
Action Input: {{"param": "value"}}

After each action, you receive an Observation. Continue until you have enough evidence.

When ready for final response:

Thought: I have completed all phases and gathered sufficient evidence
Final Answer: [Your complete structured response]

## CRITICAL RULES:
1. **Follow all 5 phases** — DO NOT skip any phase
2. **Minimum 2 tools** — Call at least 2 tools before suggesting commands
3. **Honor user requests** — If user asks for X, suggest X (not something else)
4. **Cite actual data** — Include real values from tool results, not "result"
5. **Classify evidence** — Mark each piece as FACT or HINT
6. **One command per turn** — Wait for output before next command
7. **Never assume** — If something is unknown, say so
8. **ALWAYS use suggest_ssh_command tool** — NEVER write commands as plain text!
9. **Check for runbooks FIRST** — When user asks to restart/check/fix something, search for a runbook

## Data Classification (MUST USE):
- **← FACT**: Data from metrics, logs, changes, alerts (current, verified)
- **← HINT**: Data from similar incidents, proven solutions (historical, may not apply)
- **← REFERENCE**: Runbooks, docs (may need adaptation)

## REQUIRED Output Format for Final Answer:

```
**Alert Summary:** [one-line description or "No alert - user-reported issue"]

**Target:**
- Server: [server name]
- OS: [Linux/Windows/Unknown]
- Source: [Alert/User specified/Knowledge base]

**Evidence Gathered:**

Current State (verified):
- [tool_name]: [ACTUAL DATA from tool] ← FACT
- [tool_name]: [ACTUAL DATA from tool] ← FACT

Historical Reference (may or may not apply):
- [tool_name]: [summary of findings] ← HINT
- [tool_name]: [summary of findings] ← HINT

**Hypothesis:**
[Your analysis based on the evidence above]

**Recommended Action:**
- Server: [target server]
- Command: `[the exact command]`
- Explanation: [why this command]

**Risks & Rollback:**
[What could go wrong and how to recover]

**Verification:**
[Command or check to confirm success]
```

## Runbook Link Rule:
If you reference a runbook and a view URL is available, include it as:
`📖 **[View Runbook →](/runbooks/<id>/view)** (Open in AIOps Platform)`

This link should be opened in the main AIOps platform interface where the user is logged in.
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
        else:
            base_prompt += """
## Context:
No alert context - this is a user-initiated request. Focus on what the user is asking for.
"""

        # Add phase reminder
        base_prompt += """
## REMINDER: You MUST show progress through each phase:
1. 🔍 IDENTIFY - State what we're troubleshooting
2. ✅ VERIFY - Confirm target environment  
3. 📊 INVESTIGATE - Call tools and gather evidence (minimum 2 tools!)
4. 🧠 PLAN - Analyze evidence with citations
5. 🛠️ ACT - Suggest the command the user asked for

DO NOT jump to Phase 4 or 5 without completing Phases 1-3 first.
"""

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

                # Add instruction to continue with phase awareness
                if iterations == 1:
                    prompt = self.context + """Begin your investigation by following the 5-phase protocol.

Start with PHASE 1: IDENTIFY - State what we're troubleshooting.
Then use tools to gather evidence before suggesting any action.
Remember: You MUST call at least 2 tools before your Final Answer.

Thought:"""
                elif len(self.tool_calls_made) < 2 and iterations > 1:
                    prompt = self.context + f"""\nYou have called {len(self.tool_calls_made)} tool(s) so far. 
You MUST call at least 2 tools before providing a Final Answer.
Continue investigating.\n\nThought:"""
                else:
                    prompt = self.context + "\nThought:"

                # Call LLM
                response = await self._call_llm(prompt)

                # Add response to context
                self.context += f"Thought:{response}\n"

                # Check for final answer
                final_answer = self._parse_final_answer(response)
                if final_answer:
                    # Enforce minimum 2 tool calls before allowing final answer
                    normalized_user = (user_message or "").strip().lower()
                    is_greeting = normalized_user in {"hi", "hello", "hey", "test", "ping"} or (
                        len(normalized_user) <= 40 and any(g in normalized_user for g in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"])
                    )
                    is_capabilities = any(p in normalized_user for p in ["what can you do", "how can you help", "who are you", "help"])

                    if len(self.tool_calls_made) < 2 and not (is_greeting or is_capabilities):
                        logger.warning(f"Agent tried to finish with only {len(self.tool_calls_made)} tool calls, forcing more investigation")
                        self.context += f"""\n\n[SYSTEM]: You attempted to provide a Final Answer but have only called {len(self.tool_calls_made)} tool(s).
You MUST call at least 2 tools to gather evidence before suggesting any action.
Please continue investigating using the available tools.\n\nThought:"""
                        continue
                    
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

                # Add instruction to continue with phase awareness
                if iterations == 1:
                    prompt = self.context + """Begin your investigation by following the 5-phase protocol.

Start with PHASE 1: IDENTIFY - State what we're troubleshooting.
Then use tools to gather evidence before suggesting any action.
Remember: You MUST call at least 2 tools before your Final Answer.

Thought:"""
                elif len(self.tool_calls_made) < 2 and iterations > 1:
                    prompt = self.context + f"""\nYou have called {len(self.tool_calls_made)} tool(s) so far. 
You MUST call at least 2 tools before providing a Final Answer.
Continue investigating.\n\nThought:"""
                else:
                    prompt = self.context + "\nThought:"

                # Call LLM
                response = await self._call_llm(prompt)

                # Add response to context
                self.context += f"Thought:{response}\n"

                # Check for final answer
                final_answer = self._parse_final_answer(response)
                if final_answer:
                    # Enforce minimum 2 tool calls before allowing final answer
                    if len(self.tool_calls_made) < 2:
                        self.context += f"""\n\n[SYSTEM]: You attempted to provide a Final Answer but have only called {len(self.tool_calls_made)} tool(s).
You MUST call at least 2 tools to gather evidence before suggesting any action.
Please continue investigating using the available tools.\n\nThought:"""
                        continue
                    yield final_answer
                    return

                # Check for action
                action = self._parse_action(response)
                if action:
                    action_name, arguments = action
                    self.tool_calls_made.append(action_name)

                    # Get data classification for this tool
                    from app.services.agentic.progress_messages import get_data_classification, get_tool_message
                    classification = get_data_classification(action_name)
                    tool_msg = get_tool_message(action_name)

                    # Notify about tool call with classification
                    yield f"\n{tool_msg}\n"

                    # Execute tool
                    result = await self.tool_registry.execute(action_name, arguments)

                    # Add observation to context
                    self.context += f"\nObservation: {result}\n"

                    continue

                # No action and no final answer
                if "recommend" in response.lower() or "suggest" in response.lower():
                    # Enforce minimum 2 tool calls even for implicit final answers
                    if len(self.tool_calls_made) < 2:
                        self.context += f"""\n\n[SYSTEM]: You are trying to make a recommendation but have only called {len(self.tool_calls_made)} tool(s).
You MUST call at least 2 tools to gather evidence first.
Please continue investigating.\n\nThought:"""
                        continue
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
