"""
Agent Service - Core orchestration logic for Agent Mode

This service manages the autonomous agent loop that:
1. Receives a goal from the user
2. Thinks (calls LLM) to determine next action
3. Executes commands (with approval if required)
4. Analyzes output and decides next step
5. Repeats until goal is complete or stopped
"""
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, AsyncGenerator, Callable, Awaitable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import LLMProvider, Alert
from app.models_chat import ChatSession, ChatMessage
from app.models_agent import AgentSession, AgentStep, AgentStatus, StepType, StepStatus
from app.services.llm_service import get_api_key_for_provider
from app.services.executor_base import BaseExecutor
from app.services.ollama_service import ollama_completion_stream
from langchain_community.chat_models import ChatLiteLLM
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger(__name__)


# Agent system prompt for structured output
AGENT_SYSTEM_PROMPT = """You are an autonomous SRE Agent called Antigravity. You are given a troubleshooting goal and must accomplish it step by step.

## Response Format
You MUST respond with valid JSON in this exact format - NO other text before or after:
```json
{
    "action": "command",
    "content": "the shell command to run",
    "reasoning": "brief explanation of why you chose this action"
}
```

## Available Actions:
- **command**: Run a shell command on the server. Use this to investigate or fix issues.
- **question**: Ask the user a critical question if you need information you cannot determine from commands.
- **complete**: The goal has been achieved. Include a summary in "content".
- **failed**: The goal cannot be achieved. Explain why in "content".

## Rules:
1. ALWAYS respond with ONLY the JSON format above - no markdown, no explanations outside the JSON.
2. Take ONE step at a time. After each command, you will receive the output to analyze.
3. Be efficient - don't run unnecessary commands.
4. If a command fails, try an alternative approach before giving up.
5. When the goal is achieved, use "complete" action with a summary of what was done.
6. Use "question" sparingly - only when you absolutely need user input.

## Safety:
- Do NOT run destructive commands (rm -rf /, drop database, etc.) without explicit user confirmation.
- Prefer investigative commands first (ls, cat, df, ps, etc.) before making changes.
- Always verify before modifying critical files.

## Context Format:
You will receive:
- GOAL: The objective to achieve
- ALERT_CONTEXT: Information about the alert being investigated (if any)
- COMMAND_HISTORY: Previous commands and their outputs from this session
- CURRENT_OUTPUT: The output from the most recent command (if any)

Analyze all context carefully before deciding your next action.
"""


def get_agent_system_prompt(goal: str, alert: Optional[Alert] = None, server_info: Optional[Dict] = None) -> str:
    """Build the complete system prompt with goal, alert, and server context."""
    prompt = AGENT_SYSTEM_PROMPT
    
    # Add server context if available
    if server_info:
        os_type = server_info.get('os_type', 'linux')
        protocol = server_info.get('protocol', 'ssh')
        hostname = server_info.get('hostname', 'server')
        
        prompt += f"""
## SERVER CONTEXT:
- Hostname: {hostname}
- OS Type: {os_type}
- Protocol: {protocol}

**IMPORTANT**: This is a **{os_type.upper()}** server.
"""
        if os_type.lower() == 'windows':
            prompt += """- Use **PowerShell** or **CMD** commands (e.g., Get-Volume, Get-Process, wmic, systeminfo)
- Do NOT use Linux commands like df, ps, top, etc.
"""
        else:
            prompt += """- Use **bash/shell** commands (e.g., df, ps, top, free, etc.)
"""
    
    prompt += f"\n\n## GOAL:\n{goal}\n"
    
    if alert:
        prompt += f"""
## ALERT_CONTEXT:
- Name: {alert.alert_name}
- Severity: {alert.severity}
- Instance: {alert.instance}
- Status: {alert.status}
- Summary: {alert.annotations_json.get('summary', 'N/A')}
- Description: {alert.annotations_json.get('description', 'N/A')}

## INITIAL ANALYSIS:
{alert.ai_analysis or 'No prior analysis available.'}
"""
    
    return prompt


def parse_agent_response(response_text: str) -> Dict[str, Any]:
    """
    Parse the agent's JSON response.
    
    Returns:
        dict with keys: action, content, reasoning
        
    Raises:
        ValueError if response cannot be parsed
    """
    # Try to extract JSON from the response
    # The LLM might wrap it in markdown code blocks
    
    # Remove markdown code block if present
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find bare JSON object
        json_match = re.search(r'\{[^{}]*"action"[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            # Last resort: try the whole response
            json_str = response_text.strip()
    
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse agent response: {e}")
        logger.debug(f"Raw response: {response_text}")
        raise ValueError(f"Invalid JSON response from agent: {e}")
    
    # Validate required fields
    if 'action' not in data:
        raise ValueError("Agent response missing 'action' field")
    if 'content' not in data:
        raise ValueError("Agent response missing 'content' field")
    
    action = data.get('action', '').lower()
    if action not in ['command', 'question', 'complete', 'failed']:
        raise ValueError(f"Invalid action: {action}")
    
    return {
        'action': action,
        'content': data.get('content', ''),
        'reasoning': data.get('reasoning', '')
    }


class AgentService:
    """
    Orchestrates the autonomous agent troubleshooting loop.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._notify_callback: Optional[Callable[[str, dict], Awaitable[None]]] = None
        
    def set_notify_callback(self, callback: Callable[[str, dict], Awaitable[None]]):
        """Set callback for notifying frontend of updates."""
        self._notify_callback = callback
        
    async def notify(self, event_type: str, data: dict):
        """Send notification to frontend."""
        if self._notify_callback:
            try:
                await self._notify_callback(event_type, data)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
    
    async def create_session(
        self,
        chat_session_id: UUID,
        user_id: UUID,
        server_id: UUID,
        goal: str,
        auto_approve: bool = False,
        max_steps: int = 20
    ) -> AgentSession:
        """Create a new agent session."""
        session = AgentSession(
            chat_session_id=chat_session_id,
            user_id=user_id,
            server_id=server_id,
            goal=goal,
            auto_approve=auto_approve,
            max_steps=max_steps,
            status=AgentStatus.IDLE.value
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(f"Created agent session {session.id} with goal: {goal[:50]}...")
        return session
    
    async def get_session(self, session_id: UUID) -> Optional[AgentSession]:
        """Get an agent session by ID."""
        return self.db.query(AgentSession).filter(AgentSession.id == session_id).first()
    
    async def update_status(self, session: AgentSession, status: AgentStatus):
        """Update agent session status."""
        session.status = status.value
        session.updated_at = datetime.utcnow()
        self.db.commit()
        
        await self.notify("status_changed", {
            "session_id": str(session.id),
            "status": status.value
        })
    
    def build_context(self, session: AgentSession) -> str:
        """Build context string from session history."""
        context_parts = []
        
        # Add command history
        if session.steps:
            context_parts.append("## COMMAND_HISTORY:")
            for step in session.steps:
                if step.step_type == StepType.COMMAND.value:
                    context_parts.append(f"\n### Step {step.step_number}:")
                    context_parts.append(f"Command: {step.content}")
                    if step.output:
                        # Truncate long output
                        output = step.output
                        if len(output) > 2000:
                            output = output[:1000] + "\n...[truncated]...\n" + output[-1000:]
                        context_parts.append(f"Output:\n```\n{output}\n```")
                        if step.exit_code is not None:
                            context_parts.append(f"Exit Code: {step.exit_code}")
                    context_parts.append("")
        
        return "\n".join(context_parts)
    
    async def think(self, session: AgentSession, provider: LLMProvider) -> Dict[str, Any]:
        """
        Call LLM to determine next action.
        
        Returns:
            dict with keys: action, content, reasoning
        """
        await self.update_status(session, AgentStatus.THINKING)
        
        # Get alert context if available
        chat_session = session.chat_session
        alert = chat_session.alert if chat_session else None
        
        # Get server info for OS-aware commands
        server_info = None
        if session.server_id:
            from app.models import ServerCredential
            server = self.db.query(ServerCredential).filter(ServerCredential.id == session.server_id).first()
            if server:
                server_info = {
                    'hostname': server.hostname,
                    'os_type': getattr(server, 'os_type', 'linux') or 'linux',
                    'protocol': getattr(server, 'protocol', 'ssh') or 'ssh'
                }
        
        # Build system prompt with server context
        system_prompt = get_agent_system_prompt(session.goal, alert, server_info)
        
        # Build context from history
        context = self.build_context(session)
        
        # Build the user message - combine context and instruction
        user_content_parts = []
        
        # Add context only if there's actual command history
        if context and context.strip():
            user_content_parts.append(context)
        
        # Add instruction to generate next step
        if session.current_step_number == 0:
            user_content_parts.append("The agent session has started. Analyze the goal and alert context, then provide your first action as JSON.")
        else:
            last_step = session.steps[-1] if session.steps else None
            if last_step and last_step.output:
                user_content_parts.append("The previous command has completed. Analyze the output above and provide your next action as JSON.")
            elif last_step and last_step.status == StepStatus.REJECTED.value:
                user_content_parts.append("The user rejected/skipped the previous command. Please propose an alternative approach as JSON.")
            else:
                user_content_parts.append("Provide your next action as JSON.")
        
        # Combine into a single user message to avoid empty content issues
        user_message = "\n\n".join(user_content_parts)
        
        # Build messages - just system + one user message
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # Call LLM
        full_response = ""
        
        try:
            if provider.provider_type == "ollama":
                from app.services.ollama_service import ollama_completion
                
                config = provider.config_json or {}
                full_response = await ollama_completion(
                    provider=provider,
                    messages=messages,
                    temperature=config.get("temperature", 0.3),
                    max_tokens=config.get("max_tokens", 500)
                )
            else:
                # Use LangChain with LiteLLM
                api_key = get_api_key_for_provider(provider)
                model_name = provider.model_id
                
                print(f"[DEBUG agent_service] Using API key for {provider.name}: {api_key[:15] if api_key else 'None'}...")
                
                # LiteLLM ignores api_key param and reads from env vars, so we must set them
                import os
                if provider.provider_type == "anthropic":
                    os.environ["ANTHROPIC_API_KEY"] = api_key or ""
                elif provider.provider_type == "openai":
                    os.environ["OPENAI_API_KEY"] = api_key or ""
                elif provider.provider_type == "google":
                    os.environ["GOOGLE_API_KEY"] = api_key or ""
                
                llm = ChatLiteLLM(
                    model=model_name,
                    api_key=api_key,
                    api_base=provider.api_base_url,
                    temperature=provider.config_json.get("temperature", 0.3),
                    max_tokens=provider.config_json.get("max_tokens", 500),
                )
                
                lc_messages = []
                for msg in messages:
                    if msg["role"] == "system":
                        lc_messages.append(SystemMessage(content=msg["content"]))
                    elif msg["role"] == "user":
                        lc_messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        lc_messages.append(AIMessage(content=msg["content"]))
                
                response = await llm.ainvoke(lc_messages)
                full_response = response.content
            
            logger.debug(f"Agent LLM response: {full_response[:200]}...")
            
            # Parse the response
            return parse_agent_response(full_response)
            
        except Exception as e:
            logger.error(f"Agent think error: {e}", exc_info=True)
            raise
    
    async def create_step(
        self,
        session: AgentSession,
        action: Dict[str, Any]
    ) -> AgentStep:
        """Create a new agent step from the LLM action."""
        session.current_step_number += 1
        
        step = AgentStep(
            agent_session_id=session.id,
            step_number=session.current_step_number,
            step_type=action['action'],
            content=action['content'],
            reasoning=action.get('reasoning', ''),
            status=StepStatus.PENDING.value
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        
        await self.notify("step_created", {
            "session_id": str(session.id),
            "step": {
                "id": str(step.id),
                "step_number": step.step_number,
                "step_type": step.step_type,
                "content": step.content,
                "reasoning": step.reasoning,
                "status": step.status
            }
        })
        
        return step
    
    async def execute_command(
        self,
        session: AgentSession,
        step: AgentStep,
        executor: BaseExecutor
    ) -> tuple[str, int]:
        """
        Execute a command on the server and capture output.
        
        Returns:
            tuple of (output, exit_code)
        """
        await self.update_status(session, AgentStatus.EXECUTING)
        step.status = StepStatus.EXECUTING.value
        self.db.commit()
        
        command = step.content
        logger.info(f"Agent executing command: {command}")
        
        try:
            # Ensure connection is established
            if not executor.is_connected:
                await executor.connect()
            
            # Run command using executor (works for SSH and WinRM)
            result = await executor.execute(command, timeout=60)
            
            output = result.stdout or ""
            if result.stderr:
                output += f"\n[STDERR]: {result.stderr}"
            
            exit_code = result.exit_code
            
            step.output = output
            step.exit_code = exit_code
            step.status = StepStatus.EXECUTED.value
            step.executed_at = datetime.utcnow()
            self.db.commit()
            
            await self.notify("step_updated", {
                "session_id": str(session.id),
                "step": {
                    "id": str(step.id),
                    "step_number": step.step_number,
                    "output": output[:5000],  # Limit for notification
                    "exit_code": exit_code,
                    "status": step.status
                }
            })
            
            return output, exit_code
            
        except asyncio.TimeoutError:
            step.output = "[ERROR: Command timed out after 60 seconds]"
            step.exit_code = -1
            step.status = StepStatus.FAILED.value
            self.db.commit()
            return step.output, -1
            
        except Exception as e:
            error_msg = f"[ERROR: {type(e).__name__}: {str(e)}]"
            step.output = error_msg
            step.exit_code = -1
            step.status = StepStatus.FAILED.value
            self.db.commit()
            logger.error(f"Command execution error: {e}")
            return error_msg, -1
    
    async def approve_step(self, session: AgentSession) -> Optional[AgentStep]:
        """Approve the pending step."""
        pending_step = self.db.query(AgentStep).filter(
            AgentStep.agent_session_id == session.id,
            AgentStep.status == StepStatus.PENDING.value
        ).first()
        
        if pending_step:
            pending_step.status = StepStatus.APPROVED.value
            self.db.commit()
            
            await self.notify("step_updated", {
                "session_id": str(session.id),
                "step": {
                    "id": str(pending_step.id),
                    "status": StepStatus.APPROVED.value
                }
            })
            
        return pending_step
    
    async def reject_step(self, session: AgentSession) -> Optional[AgentStep]:
        """Reject/skip the pending step."""
        pending_step = self.db.query(AgentStep).filter(
            AgentStep.agent_session_id == session.id,
            AgentStep.status == StepStatus.PENDING.value
        ).first()
        
        if pending_step:
            pending_step.status = StepStatus.REJECTED.value
            pending_step.output = "[User rejected this command]"
            self.db.commit()
            
            await self.notify("step_updated", {
                "session_id": str(session.id),
                "step": {
                    "id": str(pending_step.id),
                    "status": StepStatus.REJECTED.value
                }
            })
            
        return pending_step
    
    async def stop_session(self, session: AgentSession):
        """Stop the agent session."""
        session.status = AgentStatus.STOPPED.value
        session.completed_at = datetime.utcnow()
        self.db.commit()
        
        await self.notify("status_changed", {
            "session_id": str(session.id),
            "status": AgentStatus.STOPPED.value
        })
    
    async def run_loop(
        self,
        session: AgentSession,
        provider: LLMProvider,
        executor: BaseExecutor
    ) -> AsyncGenerator[dict, None]:
        """
        Main agent loop - runs until complete, failed, or stopped.
        
        This is a generator that yields events for each step.
        It pauses when awaiting approval.
        """
        logger.info(f"Starting agent loop for session {session.id}")
        
        while True:
            # Check termination conditions
            if session.status in [
                AgentStatus.COMPLETED.value,
                AgentStatus.FAILED.value,
                AgentStatus.STOPPED.value
            ]:
                logger.info(f"Agent loop ending with status: {session.status}")
                break
            
            # Check step limit
            if session.current_step_number >= session.max_steps:
                session.status = AgentStatus.FAILED.value
                session.error_message = f"Reached maximum step limit ({session.max_steps})"
                session.completed_at = datetime.utcnow()
                self.db.commit()
                
                await self.notify("complete", {
                    "session_id": str(session.id),
                    "status": "failed",
                    "message": session.error_message
                })
                break
            
            try:
                # 1. Think - get next action from LLM
                action = await self.think(session, provider)
                logger.info(f"Agent action: {action['action']} - {action['content'][:50]}...")
                
                # 2. Create step
                step = await self.create_step(session, action)
                
                # 3. Handle action type
                if action['action'] == 'command':
                    # Check if approval is needed
                    if not session.auto_approve:
                        await self.update_status(session, AgentStatus.AWAITING_APPROVAL)
                        
                        yield {
                            "type": "awaiting_approval",
                            "step": step
                        }
                        
                        # Wait for approval
                        while True:
                            await asyncio.sleep(0.5)
                            self.db.refresh(session)
                            self.db.refresh(step)
                            
                            if session.status == AgentStatus.STOPPED.value:
                                break
                            
                            if step.status == StepStatus.APPROVED.value:
                                # Execute the command
                                output, exit_code = await self.execute_command(
                                    session, step, executor
                                )
                                yield {
                                    "type": "executed",
                                    "step": step,
                                    "output": output,
                                    "exit_code": exit_code
                                }
                                break
                                
                            elif step.status == StepStatus.REJECTED.value:
                                # Skip this step
                                yield {
                                    "type": "rejected",
                                    "step": step
                                }
                                break
                    else:
                        # Auto-approve mode - execute immediately
                        output, exit_code = await self.execute_command(
                            session, step, executor
                        )
                        yield {
                            "type": "executed",
                            "step": step,
                            "output": output,
                            "exit_code": exit_code
                        }
                
                elif action['action'] == 'question':
                    # Agent needs user input
                    await self.update_status(session, AgentStatus.AWAITING_APPROVAL)
                    yield {
                        "type": "question",
                        "step": step,
                        "question": action['content']
                    }
                    # Loop will continue when user provides answer
                    
                elif action['action'] == 'complete':
                    # Goal achieved!
                    session.status = AgentStatus.COMPLETED.value
                    session.summary = action['content']
                    session.completed_at = datetime.utcnow()
                    self.db.commit()
                    
                    step.status = StepStatus.EXECUTED.value
                    self.db.commit()
                    
                    await self.notify("complete", {
                        "session_id": str(session.id),
                        "status": "completed",
                        "message": action['content']
                    })
                    
                    yield {
                        "type": "complete",
                        "summary": action['content']
                    }
                    break
                    
                elif action['action'] == 'failed':
                    # Goal cannot be achieved
                    session.status = AgentStatus.FAILED.value
                    session.error_message = action['content']
                    session.completed_at = datetime.utcnow()
                    self.db.commit()
                    
                    step.status = StepStatus.EXECUTED.value
                    self.db.commit()
                    
                    await self.notify("complete", {
                        "session_id": str(session.id),
                        "status": "failed",
                        "message": action['content']
                    })
                    
                    yield {
                        "type": "failed",
                        "message": action['content']
                    }
                    break
                    
            except Exception as e:
                logger.error(f"Agent loop error: {e}", exc_info=True)
                session.status = AgentStatus.FAILED.value
                session.error_message = f"Agent error: {str(e)}"
                session.completed_at = datetime.utcnow()
                self.db.commit()
                
                await self.notify("complete", {
                    "session_id": str(session.id),
                    "status": "failed",
                    "message": session.error_message
                })
                
                yield {
                    "type": "error",
                    "message": str(e)
                }
                break
            
            # Small delay between steps to avoid hammering the LLM
            await asyncio.sleep(0.5)
