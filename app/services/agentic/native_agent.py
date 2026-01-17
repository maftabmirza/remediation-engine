"""
Native Tool Calling Agent

Uses native function/tool calling capabilities of LLM providers
(OpenAI, Anthropic, Google) for reliable structured tool invocation.
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional, AsyncGenerator, Union, Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session
from litellm import acompletion
import litellm
litellm.set_verbose = True
import anthropic

from app.models import LLMProvider, Alert
from app.services.llm_service import get_api_key_for_provider
from app.services.agentic.tools.registry import CompositeToolRegistry, create_full_registry

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
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        initial_messages: Optional[List[Dict[str, Any]]] = None,
        on_tool_call_complete: Optional[Callable[[str, Dict[str, Any], str], None]] = None,
        registry_factory: Optional[Callable] = None
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
            initial_messages: Pre-existing conversation history to restore session context
            on_tool_call_complete: Callback for tool execution logging
            registry_factory: Factory function to create tool registry (default: create_full_registry)
        """
        self.db = db
        self.provider = provider
        self.alert = alert
        self.max_iterations = max_iterations
        provider_config = provider.config_json or {}
        self.temperature = temperature if temperature is not None else provider_config.get("temperature", 0.3)
        self.max_tokens = max_tokens if max_tokens is not None else provider_config.get("max_tokens", 2000)
        self.on_tool_call_complete = on_tool_call_complete

        # Initialize tool registry
        alert_id = alert.id if alert else None
        factory = registry_factory or create_full_registry
        self.tool_registry = factory(db, alert_id=alert_id)

        # Conversation history - restore from initial_messages if provided
        self.messages: List[Dict[str, Any]] = initial_messages if initial_messages else []
        self.tool_calls_made: List[str] = []

    @classmethod
    def supports_provider(cls, provider_type: str) -> bool:
        """Check if this agent supports the given provider type"""
        return provider_type in cls.SUPPORTED_PROVIDERS

    def _get_system_prompt(self) -> str:
        """Generate the system prompt for the agent"""
        base_prompt = """You are RE-VIVE, an advanced SRE AI Agent from Antigravity.

    ## Tool-First Approach
    You are pair-programming with the user to investigate and resolve production incidents.

## ANTI-HALLUCINATION & SAFETY RULE (READ FIRST)
1. **DO NOT INVENT DATA.** You often try to "complete" the task by simulating tool outputs in your text. **STOP.**
2. **YOU MUST CALL TOOLS.** You cannot know CPU usage, runbooks, or logs until you call the tool and get a result.
3. **NO ACTION WITHOUT CONTEXT.** Do not Suggest Commands (Phase 5) until you have actually called tools in Phase 3.
4. **OUTPUT FORMAT LOCK:** Do NOT write the "Evidence Gathered" section until you have real tool results.

## EXECUTION PROTOCOL (5 Phases - All Execute Sequentially)

You MUST follow this protocol for every troubleshooting session:

### PHASE 1: IDENTIFY — What are we troubleshooting?

| Scenario | Action |
|----------|--------|
| Alert-based (alert context exists) | Call `get_alert_details` — target in alert labels |
| Application-based ("App X is slow") | Call `search_knowledge` — discover which servers run the app |
| Server-based ("Server Y is down") | Validate hostname, proceed |
| Ambiguous ("the server is down") | ASK user: "Which server are you referring to?" |
| General question | Answer or ask "On which server?" |

### PHASE 2: VERIFY — Confirm environment details

1. Check knowledge base first: `search_knowledge` for OS, environment details
2. If not found, verify via command: `suggest_ssh_command` with `uname -a` or `systeminfo`
3. Once confirmed, remember for session (don't re-check)

Output: "Target: [hostname], OS: [Linux/Windows] — from [source]"

### PHASE 3: INVESTIGATE — Gather evidence

**IMPORTANT: When user requests a specific action (restart, check, fix, etc.):**
- FIRST call `get_runbook` with the service name (e.g., "apache", "nginx", "mysql")
- If runbook exists, use it! Include the runbook link in your response.
- Search terms: try service name, server name, or action type

**Current State (FACTS - verified, trustworthy):**
- `query_grafana_metrics` — CPU, memory, latency data
- `query_grafana_logs` — Error patterns, stack traces
- `get_recent_changes` — Deployments, config changes

**Alert Context (if alert exists):**
- `get_alert_details` — Full alert metadata
- `get_correlated_alerts` — Related alerts in group
- `get_service_dependencies` — Blast radius

**Historical Reference (HINTS - may or may not apply):**
- `get_similar_incidents` — Past incidents (context may differ)
- `get_proven_solutions` — Past fixes (needs verification)
- `get_runbook` — Procedures (ALWAYS check for user-requested actions!)
- `get_feedback_history` — What worked/failed before

**CRITICAL:** Historical data informs investigation, but current state determines action.
Never say "this WILL fix it" — say "this MAY help based on past data."

### PHASE 4: PLAN — Analyze and decide

1. Form hypothesis: Rank likely causes based on evidence
2. Compare historical data: Check if past solution context matches current
3. Select next action using decision tree:
   - Need current stats? → `query_grafana_metrics`
   - Need logs? → `query_grafana_logs`
   - Need to check history? → `get_similar_incidents`, `get_proven_solutions`
   - Need procedure? → `get_runbook` (may not exist)
   - Ready to act? → `suggest_ssh_command`
4. Syntax check: Match command to confirmed OS (systemctl for Linux, Restart-Service for Windows)

### PHASE 5: ACT — Suggest command

**MANDATORY: You MUST call the `suggest_ssh_command` tool to suggest commands.**
- NEVER just write a command in text — it won't be executable!
- If you don't call the tool, the user cannot run the command.

Rules:
- Use `suggest_ssh_command` — NEVER write commands as plain text
- Commands are validated by safety filter (dangerous commands will be blocked)
- ONE command per turn — stop and wait for output
- No chaining: Never write "then run this..." or "after that..."

After suggesting: ⏳ "Waiting for your output..."

After suggesting: ⏳ "Waiting for your output..."

---

## ANTI-HALLUCINATION RULE (READ CAREFULLY)
You often try to "complete" the task by inventing tool outputs. **STOP.**
- You CANNOT know the CPU usage or Runbook content until you **call the tool** and receive the result.
- **PROHIBITED:** Writing the "Evidence Gathered" section with fake data.
- **REQUIRED:** Call `get_runbook` -> Wait -> Read Result -> Call `query_metrics` -> Wait -> Read Result.
- Only output the "OUTPUT FORMAT" section in your **FINAL** response, after all tools have finished.

## OUTPUT FORMAT (Only for Final Response)
 **DO NOT USE THIS FORMAT UNTIL ALL TOOLS ARE DONE.**

```
1. Alert Summary: [summary]

2. Target:
   - Server: [hostname]
   - OS: [verified OS]
   - Source: [source]

3. Evidence Gathered:
   (List only ACTUALLY executed tools and their REAL results)
   - [tool_name]: [brief summary of real output]
   
4. Hypothesis: [ranked causes]

5. Recommended Action: [command]

6. Risks & Rollback: [plan]

7. Verification: [plan]
```

---

## CRITICAL RULES

1. **Never assume target** — If ambiguous, ASK. Discover from knowledge base if app-level.
2. **Never act without evidence** — Gather context using tools first (minimum 2 tools before action).
3. **Cite sources** — Every claim must reference which tool provided it.
4. **Check OS before commands** — Match syntax to verified OS.
5. **Never hallucinate** — Don't invent server names, configs, or incidents.
6. **One command per turn** — Suggest one, wait for output, then continue.
7. **Historical data = hints** — Past solutions may or may not work. Verify first.
8. **ALWAYS use suggest_ssh_command tool** — NEVER write commands as plain text!
9. **Check for runbooks FIRST** — When user asks to restart/check/fix, search for a runbook.
10. **Honor user requests** — If user asks for X, do X (not something else).

---

## TOOL REFERENCE

### Knowledge Tools (may or may not return results):
- **search_knowledge**: Search runbooks, SOPs, architecture docs
- **get_runbook**: Step-by-step procedures (may not exist)
- **get_similar_incidents**: Past incidents (reference only, context may differ)
- **get_proven_solutions**: Past fixes (hints, not guarantees)
- **get_feedback_history**: What worked/failed before

### Observability Tools (current state - FACTS):
- **query_grafana_metrics**: PromQL queries for CPU, memory, latency
- **query_grafana_logs**: LogQL queries for errors, patterns
- **get_alert_details**: Alert metadata (only if alert exists)

### Investigation Tools:
- **get_recent_changes**: Deployments, config changes (FACTS)
- **get_correlated_alerts**: Related alerts (only if alert exists)
- **get_service_dependencies**: Upstream/downstream services

### Action Tool:
- **suggest_ssh_command**: Propose command for user execution (validated by safety filter)

---

## COMMAND SUGGESTION PROTOCOL

You are **NOT AUTHORIZED** to execute commands directly. You must SUGGEST them.

**Protocol Specifics:**
- **SSH (Linux/Windows)**: You CAN suggest interactive commands. The system handles interactivity.
- **WinRM (Windows)**: Commands MUST be NON-INTERACTIVE. Use `-Force`, `-Confirm:$false`, etc.

**Workflow:**
1. Call `suggest_ssh_command` with server, command, and explanation
2. Command is validated by safety filter
3. If ALLOWED: Command displayed to user with ✅ Safe
4. If SUSPICIOUS: Command displayed with ⚠️ Warning
5. If BLOCKED: User sees ⛔ COMMAND BLOCKED message, you must suggest alternative
6. STOP and wait for user output
7. Analyze output, suggest next command OR provide final recommendations




**COMMAND QUEUE PROTOCOL:**
- You MAY suggest multiple commands if they form a LOGICAL SEQUENCE
  - Example: "To fix nginx: 1) stop apache, 2) start nginx, 3) check status"
  - All commands will be added to a queue for the user
  - User can execute them one-by-one, skip some, or execute all
- **CRITICAL:** You MUST use the `suggest_ssh_command` tool for ANY executable command. Do NOT write commands in text.
- **ABSOLUTELY FORBIDDEN:** NEVER suggest tool names as shell commands!
  - BAD: `suggest_ssh_command(command="query_grafana_logs")` ❌
  - BAD: `suggest_ssh_command(command="get_similar_incidents")` ❌
  - GOOD: Call `query_grafana_logs` directly as a tool_call ✅
  - Tool names (query_grafana_metrics, query_grafana_logs, get_recent_changes, get_similar_incidents, search_knowledge, etc.) are YOUR internal tools - call them via tool_call, NEVER suggest them to users as shell commands.
- After user executes commands, they'll click **Continue** and you'll receive outputs
- Analyze the outputs and suggest next steps
- **DO NOT suggest unrelated commands in batch** - only logical sequences
- **NEVER write [CMD_CARD] markers in your text** - they're auto-generated from tools

**HARD LIMIT:** After calling `suggest_ssh_command`, your response should be SHORT. Maximum 2-3 sentences.

---

## TASK COMPLETION RULES

- **RECOGNIZE WHEN DONE**: If task succeeded, say "Done!" and stop.
- **READ TERMINAL OUTPUT**: Output tells you if task succeeded.
- **DON'T OVER-SEARCH**: Only call tools when you need information.
- **STOP WHEN DONE**: Don't suggest additional actions after success.

---

## FOLLOW-UP SUGGESTIONS

After providing a response (especially after command execution results), you MAY include follow-up suggestions using this format:

```
[SUGGESTIONS]
["Check error logs", "Restart the service", "Close investigation"]
[/SUGGESTIONS]
```

Rules for suggestions:
- Include 2-4 short action phrases (max 6 words each)
- Make them relevant to the current context
- Include "Close investigation" or "Issue resolved" when task appears complete
- Examples: "Check error logs", "Restart Apache", "View metrics", "Roll back changes", "Issue resolved"

Do NOT include suggestions if you just suggested a command - wait for the result first.

---

## RUNBOOK LINK RULE

If a tool output includes a runbook `view_url`, you MUST include a clickable Markdown link:
`View: [Open runbook](/runbooks/<id>/view)`
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
        else:
            base_prompt += """
## Context:
No alert context - this is a user-initiated request. Focus on what the user is asking for.
**HONOR USER INTENT (CONTEXT-AWARE):**
- When the user asks to restart/fix/diagnose something, don't assume commands.
- First determine the **organizational context (Standard Runbooks)** and runtime/management context (OS/platform, host vs container vs orchestration), using available tools or 1–3 targeted questions.
- Then provide the minimal safe action for that context plus a verification step (status/health check/logs/metrics), and include rollback/escalation guidance if it fails.
"""

        # Add minimum tool requirement reminder
        base_prompt += """
## MANDATORY REQUIREMENT:
You MUST call at least 2 tools to gather evidence before suggesting any command.
Tools called so far will be tracked. If you try to suggest a command without sufficient evidence, you will be asked to continue investigating.
"""

        return base_prompt

    def _extract_runbook_view_links(self) -> List[str]:
        """Extract unique runbook view URLs from tool outputs."""
        pattern = re.compile(r"\[Open runbook\]\(([^)]+)\)")
        seen: set[str] = set()
        links: List[str] = []

        for msg in self.messages:
            if msg.get("role") != "tool":
                continue
            content = str(msg.get("content") or "")
            for url in pattern.findall(content):
                if url not in seen:
                    seen.add(url)
                    links.append(url)

        return links

    def _get_last_user_message_text(self) -> str:
        """Return the last real user message (skips internal [SYSTEM] injections)."""
        for msg in reversed(self.messages):
            if msg.get("role") != "user":
                continue
            content = str(msg.get("content") or "").strip()
            if not content:
                continue
            if content.startswith("[SYSTEM]:"):
                continue
            return content
        return ""

    def _is_greeting_or_capabilities_question(self, text: str) -> bool:
        t = re.sub(r"\s+", " ", (text or "").strip().lower())
        if not t:
            return False
        # Common greetings / sanity checks
        if t in {"hi", "hello", "hey", "test", "ping"}:
            return True
        if len(t) <= 40 and any(g in t for g in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]):
            return True
        # Capability / onboarding questions
        if any(p in t for p in [
            "what can you do",
            "how can you help",
            "help",
            "who are you",
            "what are you",
            "how to use",
        ]):
            return True
        return False

    def _contains_command_like_text(self, text: str) -> bool:
        if not text:
            return False
        if "```" in text:
            return True
        lower = text.lower()
        # Very lightweight command heuristics (Linux + Windows)
        cmd_patterns = [
            r"(^|\n)\s*(sudo\s+)",
            r"(^|\n)\s*(systemctl|journalctl|kubectl|docker|curl|wget|apt-get|yum|dnf|helm)\b",
            r"(^|\n)\s*(powershell|cmd\.exe)\b",
            r"\b(restart-service|get-service|start-service|stop-service)\b",
        ]
        return any(re.search(p, lower) for p in cmd_patterns)

    def _looks_like_actionable_recommendation(self, assistant_text: str) -> bool:
        t = (assistant_text or "").strip()
        if not t:
            return False
        lower = t.lower()
        if self._contains_command_like_text(t):
            return True
        if any(k in lower for k in [
            "recommended action",
            "run this",
            "execute",
            "restart",
            "roll back",
            "rollback",
            "fix",
        ]):
            return True
        return False

    def _should_enforce_min_tool_calls(self, assistant_text: str) -> bool:
        """Only enforce min-tool rule when we're about to act (or have alert context)."""
        if self.alert:
            return True

        last_user = self._get_last_user_message_text()
        if self._is_greeting_or_capabilities_question(last_user):
            return False

        # Allow clarifying questions / onboarding without tools
        if "?" in (assistant_text or "") and not self._contains_command_like_text(assistant_text or ""):
            return False

        return self._looks_like_actionable_recommendation(assistant_text or "")

    def _ensure_runbook_links_in_final(self, final_content: str) -> str:
        """Append runbook view links to the final response if missing."""
        links = self._extract_runbook_view_links()
        if not links:
            return final_content

        missing = [url for url in links if url and url not in (final_content or "")]
        if not missing:
            return final_content

        suffix_lines = ["", "**Runbook links:**"]
        for url in missing[:10]:
            suffix_lines.append(f"- [Open runbook]({url})")

        return (final_content or "").rstrip() + "\n" + "\n".join(suffix_lines) + "\n"

    def _get_tools_for_provider(self) -> List[Dict[str, Any]]:
        """
        Get tools in the format expected by the provider.
        """
        provider_type = (self.provider.provider_type or "").lower()
        if provider_type == "anthropic":
            return self.tool_registry.get_anthropic_tools()
        return self.tool_registry.get_openai_tools()
    
    async def _call_anthropic_directly(self, api_key: str) -> Dict[str, Any]:
        """
        Call Anthropic SDK directly to avoid litellm translation bugs.
        """
        import anthropic
        import json
        
        logger.info("DEBUG: Entering _call_anthropic_directly")

        # Convert our OpenAI-style messages to Anthropic format
        anthropic_messages = []
        system_prompt = None
        
        try:
            for msg in self.messages:
                role = msg["role"]
                content = msg.get("content", "")
                
                if role == "system":
                    system_prompt = content
                    continue
                
                elif role == "tool":
                    # Convert to Anthropic tool_result format
                    tool_result_block = {
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id"),
                        "content": str(msg.get("content"))
                    }
                    
                    # Merge with previous user message if it exists (Anthropic requires alternating roles)
                    if anthropic_messages and anthropic_messages[-1]["role"] == "user":
                        prev_content = anthropic_messages[-1]["content"]
                        if isinstance(prev_content, str):
                            # Convert previous string to block list
                            anthropic_messages[-1]["content"] = [
                                {"type": "text", "text": prev_content},
                                tool_result_block
                            ]
                        elif isinstance(prev_content, list):
                            # Append to existing block list
                            prev_content.append(tool_result_block)
                    else:
                        # Create new user message
                        anthropic_messages.append({
                            "role": "user",
                            "content": [tool_result_block]
                        })

                elif role == "assistant" and msg.get("tool_calls"):
                    # Convert to Anthropic tool_use format
                    content_blocks = []
                    
                    # Add text content if present (Chain of Thought)
                    if content:
                        content_blocks.append({
                            "type": "text",
                            "text": content if isinstance(content, str) else str(content)
                        })

                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", {})
                        try:
                            input_obj = json.loads(fn.get("arguments", "{}"))
                        except:
                            input_obj = {}
                        
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id"),
                            "name": fn.get("name"),
                            "input": input_obj
                        })
                    
                    anthropic_messages.append({
                        "role": "assistant",
                        "content": content_blocks
                    })
                
                else:
                    # Simple user or assistant message
                    # Check for merge if same role
                    if anthropic_messages and anthropic_messages[-1]["role"] == role:
                         prev = anthropic_messages[-1]["content"]
                         curr = content if isinstance(content, str) else str(content)
                         
                         if isinstance(prev, str):
                             anthropic_messages[-1]["content"] = prev + "\n\n" + curr
                         elif isinstance(prev, list):
                             prev.append({"type": "text", "text": curr})
                    else:
                        anthropic_messages.append({
                            "role": role,
                            "content": content if isinstance(content, str) else str(content)
                        })
            
            logger.info(f"DEBUG: Constructed {len(anthropic_messages)} Anthropic messages")
            
            # Convert tools to Anthropic format
            anthropic_tools = []
            openai_tools = self.tool_registry.get_openai_tools()
            for tool in openai_tools:
                fn = tool.get("function", {})
                anthropic_tools.append({
                    "name": fn.get("name"),
                    "description": fn.get("description"),
                    "input_schema": fn.get("parameters", {})
                })
            
            # Call Anthropic directly
            # Set timeout to avoid infinite hangs
            client = anthropic.AsyncAnthropic(api_key=api_key, timeout=60.0, max_retries=2)
            
            # Strip provider prefix
            model_id = self.provider.model_id
            if model_id.startswith("anthropic/"):
                model_id = model_id.replace("anthropic/", "")
            
            logger.info(f"DEBUG: Calling Anthropic API (model={model_id})...")
            
            response = await client.messages.create(
                model=model_id,
                system=system_prompt or "",
                messages=anthropic_messages,
                tools=anthropic_tools,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            logger.info("DEBUG: Anthropic API returned successfully")
            logger.warning(f"DEBUG: Anthropic Raw Content: {response.content}")
            
            # Convert Anthropic response to OpenAI-like format
            text_content = ""
            tool_calls_list = []
            
            # Handle empty response (Anthropic sometimes returns [] after tool use)
            if not response.content:
                logger.warning("Anthropic returned empty content - using fallback")
                text_content = "I've suggested a command for you to run. Please execute it in the terminal and let me know the results."
            else:
                for block in response.content:
                    if block.type == "text":
                        text_content += block.text
                    elif block.type == "tool_use":
                        func_obj = type('obj', (object,), {
                            'name': block.name,
                            'arguments': json.dumps(block.input)
                        })()
                        
                        tool_call_obj = type('obj', (object,), {
                            'id': block.id,
                            'type': 'function',
                            'function': func_obj
                        })()
                        
                        tool_calls_list.append(tool_call_obj)
            
            message_obj = type('obj', (object,), {
                'role': 'assistant',
                'content': text_content or None,
                'tool_calls': tool_calls_list if tool_calls_list else None
            })()
            
            choice_obj = type('obj', (object,), {
                'message': message_obj
            })()
            
            response_obj = type('obj', (object,), {
                'choices': [choice_obj]
            })()
            
            return response_obj

        except Exception as e:
            logger.error(f"Anthropic Execution Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise e


    async def _call_llm(self) -> Dict[str, Any]:
        """Call the LLM with current messages and tools"""
        api_key = get_api_key_for_provider(self.provider)

        # For Anthropic, use direct SDK to avoid litellm bugs
        if self.provider.provider_type == "anthropic" and api_key:
            return await self._call_anthropic_directly(api_key)

        # Prepare tools
        tools = self._get_tools_for_provider()
        
        # Prepare messages
        # With newer LiteLLM, we can pass standard messages
        messages_to_send = self.messages

        kwargs = {
            "model": self.provider.model_id,
            "messages": messages_to_send,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "tools": tools,
        }

        if api_key:
            kwargs["api_key"] = api_key
            # Fix: Set environment variable for LiteLLM/Anthropic which sometimes ignores the kwarg
            if self.provider.provider_type == "anthropic":
                import os
                os.environ["ANTHROPIC_API_KEY"] = api_key
            elif self.provider.provider_type == "openai":
                import os
                os.environ["OPENAI_API_KEY"] = api_key

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

            # Invoke callback if provided (e.g., for logging to DB)
            if self.on_tool_call_complete:
                try:
                    self.on_tool_call_complete(tool_name, arguments, str(result))
                except Exception as e:
                    logger.error(f"Error in tool completion callback: {e}")

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

        # DEBUG: Log full conversation being sent to LLM
        logger.info("="*80)
        logger.info("AGENT DEBUG: Full conversation history sent to LLM:")
        logger.info("="*80)
        for i, msg in enumerate(self.messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            logger.info(f"Message {i} [{role}]:")
            if len(content) > 500:
                logger.info(f"  {content[:250]}...<truncated>...{content[-250:]}")
            else:
                logger.info(f"  {content}")
            
            if msg.get("tool_calls"):
                logger.info(f"  Tool calls: {len(msg['tool_calls'])} calls")
        logger.info("="*80)

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
                    # Enforce minimum tool calls only when the response is actionable.
                    if len(self.tool_calls_made) < 2 and self._should_enforce_min_tool_calls(message.content or ""):
                        logger.warning(f"Agent tried to finish with only {len(self.tool_calls_made)} tool calls, forcing more investigation")
                        # Add system message to force more investigation
                        self.messages.append({
                            "role": "user",
                            "content": f"[SYSTEM]: You attempted to provide a final answer but have only called {len(self.tool_calls_made)} tool(s). You MUST call at least 2 tools to gather evidence before suggesting any action. Please continue investigating using the available tools. Focus on the current state tools (query_grafana_metrics, query_grafana_logs, or get_recent_changes) and historical tools (get_similar_incidents, get_proven_solutions)."
                        })
                        continue
                    
                    final_content = self._ensure_runbook_links_in_final(message.content or "")

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

        # DEBUG: Log full conversation being sent to LLM
        logger.warning("="*80)
        logger.warning(f"🔍 AGENT DEBUG: Sending {len(self.messages) + 1} messages to LLM (History + New)")
        for i, msg in enumerate(self.messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            logger.warning(f"  History {i} [{role}]: {content[:50]}...")
        logger.warning(f"  New User Msg: {user_message[:50]}...")
        logger.warning("="*80)

        # Add user message
        self.messages.append({
            "role": "user",
            "content": user_message
        })

        # DEBUG: Log full conversation being sent to LLM
        logger.warning("="*80)
        logger.warning("🔍 AGENT DEBUG: Full conversation sent to LLM")
        logger.warning("="*80)
        for i, msg in enumerate(self.messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            logger.warning(f"Message {i} [{role}]: {len(content)} chars")
            if len(content) > 300:
                logger.warning(f"  START: {content[:150]}")
                logger.warning(f"  ...END: {content[-150:]}")
            else:
                logger.warning(f"  {content}")
        logger.warning("="*80)

        iterations = 0
        self.tool_calls_made = []
        stuck_warnings = 0  # Track how many times model promised tools but didn't call them

        try:
            while iterations < self.max_iterations:
                iterations += 1

                # Call LLM (non-streaming for tool detection)
                response = await self._call_llm()
                message = response.choices[0].message

                tool_calls = getattr(message, 'tool_calls', None)

                if tool_calls:
                    # User-friendly tool descriptions
                    friendly_tool_names = {
                        "get_runbook": "📖 Checking documented procedures...",
                        "search_knowledge": "📚 Searching knowledge base...",
                        "get_similar_incidents": "🔎 Looking for similar past incidents...",
                        "get_recent_changes": "📋 Checking recent changes/deployments...",
                        "get_correlated_alerts": "🔗 Checking related alerts...",
                        "query_grafana_metrics": "📊 Fetching metrics data...",
                        "query_grafana_logs": "📜 Searching logs...",
                        "get_service_dependencies": "🔌 Checking service dependencies...",
                        "get_feedback_history": "💬 Checking past feedback...",
                        "get_alert_details": "🚨 Getting alert details...",
                        "get_proven_solutions": "🏆 Checking what worked before...",
                    }
                    
                    # Notify about tool calls (skip for suggest_ssh_command since CMD_CARD handles it)
                    for tc in tool_calls:
                        tool_name = tc.function.name if hasattr(tc, 'function') else tc.get('name', 'unknown')
                        if tool_name != "suggest_ssh_command":
                            friendly_msg = friendly_tool_names.get(tool_name, f"🔍 Using {tool_name}...")
                            yield f"\n\n*{friendly_msg}*  \n"  # Double newline before + trailing spaces for markdown line break

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

                    # YIELD CONTENT FIRST: If the LLM provided an explanation/reasoning, show it BEFORE the tools/cards
                    if message.content:
                        yield message.content

                    # Execute all tools (including multiple suggest_ssh_command if present)
                    tool_results = await self._execute_tool_calls(tool_calls)

                    # Yield CMD_CARD for each suggest_ssh_command
                    command_suggested = False
                    for tc in tool_calls:
                        tool_name = tc.function.name if hasattr(tc, 'function') else tc.get('name', 'unknown')
                        if tool_name == "suggest_ssh_command":
                            command_suggested = True
                            try:
                                args = json.loads(tc.function.arguments) if hasattr(tc, 'function') else {}
                                command = args.get("command", "")
                                
                                # Apply same --no-pager fixes as tool_registry
                                if 'systemctl' in command and '--no-pager' not in command:
                                    command = command.replace('systemctl ', 'systemctl --no-pager ', 1)
                                if 'journalctl' in command and '--no-pager' not in command:
                                    command = command.replace('journalctl ', 'journalctl --no-pager ', 1)
                                
                                card_data = {
                                    "command": command,
                                    "server": args.get("server", ""),
                                    "explanation": args.get("explanation", "")
                                }
                                yield f"\n[CMD_CARD]{json.dumps(card_data)}[/CMD_CARD]\n"
                            except Exception as e:
                                logger.error(f"Failed to yield CMD_CARD: {e}")

                    # Add tool results to messages
                    for result in tool_results:
                        self.messages.append(result)

                    # If command was suggested, we're done - don't continue the loop
                    if command_suggested:
                        logger.info("Command(s) suggested via tool, ending agent loop")
                        return

                    continue

                else:
                    # No tool calls - final response
                    content = message.content or ""
                    
                    # Check if model wrote CMD_CARD markers directly in text (hallucination workaround)
                    # This happens when model doesn't use proper tool_call mechanism
                    if "[CMD_CARD]" in content:
                        logger.warning("Model wrote CMD_CARD markers in text instead of using tool_call - treating as valid response")
                        # Extract and yield the content with CMD_CARD markers
                        final_content = self._ensure_runbook_links_in_final(content)
                        self.messages.append({
                            "role": "assistant",
                            "content": final_content
                        })
                        yield final_content
                        return
                    
                    # Detect "stuck" pattern: model promises to use tools but doesn't actually call them
                    # This happens with weaker models that write "let me use X tool" instead of calling it
                    stuck_phrases = [
                        "let me continue", "let me check", "i'll use", "i will use",
                        "using the available tools", "once i have the results",
                        "let me query", "let me search", "i'll query", "i'll search"
                    ]
                    content_lower = content.lower()
                    is_stuck = any(phrase in content_lower for phrase in stuck_phrases) and len(self.tool_calls_made) < 2
                    
                    if is_stuck:
                        stuck_warnings += 1
                        logger.warning(f"Model appears stuck ({stuck_warnings}/2) - promising tools but not calling them. Tool calls: {len(self.tool_calls_made)}")
                        
                        if stuck_warnings >= 2:
                            # Model is hopelessly stuck, just return what it gave us
                            logger.warning("Model stuck after 2 warnings - returning current response")
                            final_content = self._ensure_runbook_links_in_final(content)
                            final_content += "\n\n*[Note: I was unable to query the tools directly. Please check manually.]*"
                            self.messages.append({"role": "assistant", "content": final_content})
                            yield final_content
                            return
                        
                        # Force it to call tools by being very explicit
                        self.messages.append({
                            "role": "user", 
                            "content": (
                                "[SYSTEM CRITICAL]: You said you would use tools but did NOT make any tool calls. "
                                "STOP describing what you will do. ACTUALLY CALL the tools NOW using tool_call. "
                                "If you cannot call tools, provide your best recommendation based on what you know. "
                                "Do NOT say 'let me check' or 'once I have results' - either CALL the tool or give your answer."
                            )
                        })
                        continue
                    
                    # Enforce minimum tool calls only when the response is actionable.
                    if len(self.tool_calls_made) < 2 and self._should_enforce_min_tool_calls(content):
                        logger.warning(f"Stream: Agent tried to finish with only {len(self.tool_calls_made)} tool calls, forcing more investigation")
                        # Add system message to force more investigation
                        self.messages.append({
                            "role": "user",
                            "content": f"[SYSTEM]: You attempted to provide a final answer but have only called {len(self.tool_calls_made)} tool(s). You MUST call at least 2 tools to gather evidence before suggesting any action. Please continue investigating using the available tools. Focus on the current state tools (query_grafana_metrics, query_grafana_logs, or get_recent_changes) and historical tools (get_similar_incidents, get_proven_solutions)."
                        })
                        # Don't show internal message to user - just continue silently
                        continue
                    
                    # Final response - yield content
                    final_content = self._ensure_runbook_links_in_final(content)

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
            # Enhanced error logging to debug connection issues
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Agent stream error details: {error_trace}")
            
            # Try to extract message safely
            error_msg = str(e)
            if hasattr(e, 'message'):
                error_msg = e.message
            elif hasattr(e, 'body'):
                error_msg = str(e.body)
                
            logger.error(f"Agent stream error: {error_msg}")
            
            yield f"\n\n*Error: {error_msg}*"

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
