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
        self.tool_registry = create_full_registry(db, alert_id=alert_id)

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
- **Suggest commands** using `suggest_ssh_command` - Use this to recommend commands for the user to run manually
- Search the knowledge base for runbooks and SOPs
- Find similar past incidents and their resolutions
- Check recent changes/deployments
- Query metrics and logs from Grafana
- Get correlated alerts and root cause analysis
- Find service dependencies

## Runbook Link Rule (IMPORTANT):
If a tool output includes a runbook `view_url`, or you recommend/reference a runbook, you MUST include a clickable Markdown link to the runbook view page (e.g., `View: [Open runbook](/runbooks/<id>/view)`).
This ensures the user can immediately click through to the full runbook page.

## Tool Purpose Guide - What Each Tool Provides:

### Quick Solutions (check first for problems):
- **get_proven_solutions**: 🏆 BEST FIRST CHECK - Find solutions that WORKED before for similar problems. If we've solved this before, use that solution!
- **get_runbook**: Documented step-by-step procedures for known issues. SUCCESS EXAMPLE: "nginx 502 error" → runbook had exact fix.
- **search_knowledge**: Internal wikis, environment-specific configs, custom scripts. SUCCESS EXAMPLE: "deploy to staging" → found company's specific deployment script.

### Historical Context:
- **get_similar_incidents**: Past incidents and what resolved them. SUCCESS EXAMPLE: "high CPU on api-server" → similar incident last month was a memory leak.
- **get_feedback_history**: What worked/didn't work in past troubleshooting sessions.

### Current State:
- **get_recent_changes**: Deployments, config changes in last 24h. Answers "what changed recently?"
- **get_correlated_alerts**: Other alerts in same incident group. Answers "is this part of a bigger issue?"
- **get_alert_details**: Full metadata of current alert being investigated.
- **get_service_dependencies**: Upstream/downstream services. Answers "what else could be affected?"

### Real-Time Data:
- **query_grafana_metrics**: Actual CPU, memory, latency data via PromQL. Validates hypotheses.
- **query_grafana_logs**: Error patterns, stack traces via LogQL. Finds specific error messages.

### Actions:
- **suggest_ssh_command**: Recommend commands for user to run manually.

## Think-First Approach:

Before taking action, briefly consider:
1. **Have we solved this before?** → Check `get_proven_solutions` first!
2. **What does the user need?** (Quick action vs investigation)
3. **What information might help?** (Existing docs? History? Real-time data?)
4. **Which tools could provide this?** (Use your judgment - you know the tools better now)

You are intelligent - use your reasoning to choose the right tools. Don't call tools just because they exist. Don't skip tools that could have answers. Think, then act.

**For simple requests** ("install nginx", "check disk space") → Just suggest the command
**For problems/investigations** ("nginx not working", "why is it slow") → Check proven_solutions first, then investigate

## Command Suggestion Strategy:
**PROTOCOL**: You are **NOT AUTHORIZED** to execute commands directly. You must SUGGEST them for the user to run.

**Protocol Specifics:**
- **SSH (Linux/Windows)**: You CAN suggest interactive commands (e.g., scripts that ask for input, `sudo` requiring password). The system has a "Try-Adapt" mechanism that will detect interactivity and prompt the user for input via the UI.
- **WinRM (Windows)**: You MUST ensure commands are **NON-INTERACTIVE**. Use flags like `-Force`, `-Confirm:$false`, `/quiet`, `/norestart` etc. Interactive commands will fail or timeout. If a task requires complex interactivity (e.g., GUI wizards), suggest the user connects via RDP instead.

**Workflow:**
1. **Search**: `search_knowledge` first if relevant.
2. **Suggest ONE Command**: Use `suggest_ssh_command` tool to propose EXACTLY ONE command.
3. **STOP**: Do NOT suggest additional commands. Do NOT explain future steps yet.
4. **Wait**: The user will run the command in their terminal and provide the output (automatically included in context).
5. **Analyze**: Read the provided output and suggest the NEXT single command, OR provide final recommendations.

**CRITICAL RULES:**
- **NEVER** try to execute commands yourself.
- **ALWAYS** use `suggest_ssh_command` tool for EACH command - DO NOT just write commands in markdown.
- If you need to suggest a command, you MUST call the `suggest_ssh_command` tool. Do NOT write the command in a code block without calling the tool.
- **SUGGEST ONLY ONE COMMAND PER RESPONSE** - After suggesting one command, STOP and wait for output.
- **DO NOT** write "Once you've run that, please run..." or "After that, run..." - these violate the one-command-at-a-time rule.
- **Wait** for the output before proceeding to the next step.

**Example (CORRECT):**
- User: "Install Apache"
- You: Call `suggest_ssh_command` with command="sudo apt-get update" and explanation="Update package lists first"
  ```bash
  sudo apt-get update
  ```
  Let me know when it's done."
- *(User runs command, output auto-injected)*
- User: "Done"
- You: "Good. Now install Apache (SSH handles 'Y/n' prompts interactively via UI):
  ```bash
  sudo apt-get install apache2
  ```
  "
- *(System detects prompt, user enters 'Y', command completes)*

**Example (INCORRECT - DO NOT DO THIS):**
- You: "Run this: `sudo apt-get update`, then run `sudo apt-get install apache2`..." ❌

**HARD LIMIT:** After calling `suggest_ssh_command`, your response should be SHORT - display the command and STOP. Maximum 2-3 sentences after the tool call.

## Guidelines:
- Start by understanding what information you need
- Call tools as needed - you don't need to call all of them
- After gathering information, synthesize and provide actionable recommendations
- Keep responses concise and focused
- Use **bold** for key concepts and `code blocks` for commands

## Task Completion Rules:
- **RECOGNIZE WHEN A TASK IS DONE**: If the user asked to uninstall something and you successfully uninstalled it, THE TASK IS COMPLETE. Say "Done" and stop.
- **DO NOT CONTRADICT THE USER'S REQUEST**: If user asked to uninstall Apache, do NOT suggest installing Apache afterwards.
- **DO NOT OVER-SEARCH**: Only call `search_knowledge` when you don't know how to do something. If the user's request was simple and you executed it, don't search.
- **READ THE TERMINAL OUTPUT**: The command output tells you if the task succeeded. If it shows "Removing apache2..." and completes, the task is done.
- **STOP WHEN DONE**: After a simple task is complete, say "Done! Apache has been uninstalled." and wait for the next user request.

## Format:
When you have enough information to respond:
1. Summarize what you found (cite actual command outputs)
2. Provide your hypothesis/diagnosis
3. Give specific remediation steps (execute verification commands if needed)
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

    async def _get_tools_for_provider(self) -> List[Dict[str, Any]]:
        """
        Get tools in the format expected by the provider.
        
        NOTE: LiteLLM expects tools in OpenAI format (type="function") 
        and handles the conversion to provider-specific formats (like Anthropic) internally.
        """
        # Always return OpenAI format for LiteLLM
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
            openai_tools = await self._get_tools_for_provider()
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
        tools = await self._get_tools_for_provider()
        
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
                            yield f"\n*{friendly_msg}*\n"

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

                    # Check for suggest_ssh_command and yield structured card
                    for tc in tool_calls:
                        tool_name = tc.function.name if hasattr(tc, 'function') else tc.get('name', 'unknown')
                        if tool_name == "suggest_ssh_command":
                            try:
                                args = json.loads(tc.function.arguments) if hasattr(tc, 'function') else {}
                                card_data = {
                                    "command": args.get("command", ""),
                                    "server": args.get("server", ""),
                                    "explanation": args.get("explanation", "")
                                }
                                yield f"\n[CMD_CARD]{json.dumps(card_data)}[/CMD_CARD]\n"
                            except Exception as e:
                                logger.error(f"Failed to yield CMD_CARD: {e}")

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
