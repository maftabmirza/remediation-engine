"""
Agent Service - Core orchestration logic for Agent Mode

Enhanced with IVIPA Workflow:
1. IDENTIFY - Understand what the problem is
2. VERIFY - Confirm environment and context
3. INVESTIGATE - Gather evidence (minimum 2 tools required before planning)
4. PLAN - Create hypothesis and validate against SOPs
5. ACT - Execute remediation with safety checks

Key improvements inspired by VS Code Copilot:
- Visible thinking at each phase
- Structured workflow enforcement
- Investigation policy (min 2 evidence-gathering steps)
- Plan mode with approval
- Self-correction capabilities
"""
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, AsyncGenerator, Callable, Awaitable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import LLMProvider, Alert
from app.models_chat import ChatSession, ChatMessage
from app.models_agent import AgentSession, AgentStep, AgentStatus, StepType, StepStatus, IVIPAPhase
from app.services.llm_service import get_api_key_for_provider
from app.services.ssh_service import SSHClient, get_ssh_connection
from app.services.ollama_service import ollama_completion_stream
from langchain_community.chat_models import ChatLiteLLM
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger(__name__)


# Minimum investigation tools required before moving to PLAN phase
MIN_INVESTIGATION_TOOLS = 2


# IVIPA-Aware Agent System Prompt
AGENT_SYSTEM_PROMPT = """You are an autonomous SRE Agent called Antigravity. You follow the IVIPA workflow for structured troubleshooting.

## IVIPA WORKFLOW (You MUST follow this order)

### Phase 1: IDENTIFY (What is the problem?)
- Understand the alert/goal
- Review alert details and metadata
- Search knowledge base for relevant SOPs

### Phase 2: VERIFY (Where is it happening?)
- Confirm the target environment (Linux/Windows)
- Verify server connectivity
- Check service status

### Phase 3: INVESTIGATE (Gather evidence - MINIMUM 2 STEPS REQUIRED)
- Query metrics (Prometheus/Grafana)
- Search logs (Loki)
- Check for recent changes/deployments
- Find similar past incidents
- Identify correlated alerts
- Map service dependencies
⚠️ You MUST complete at least 2 investigation steps before moving to PLAN phase.

### Phase 4: PLAN (Create hypothesis)
- Synthesize evidence into hypothesis
- Retrieve relevant runbook
- Review past feedback on similar issues
- Present plan for approval

### Phase 5: ACT (Execute with safety)
- Execute remediation commands
- All commands go through Safety Validator
- Verify changes after execution

## Response Format
You MUST respond with valid JSON:
```json
{
    "phase": "identify|verify|investigate|plan|act",
    "thinking": "Your detailed reasoning process - this is shown to the user",
    "action": "command|tool_call|question|plan|complete|failed",
    "tool_name": "name of tool if action is tool_call",
    "content": "the command, tool parameters, question, or message",
    "reasoning": "brief summary of why you chose this action"
}
```

## Available Actions:
- **command**: Run a shell command on the server
- **tool_call**: Call a specialized tool (see Available Tools below)
- **question**: Ask the user a critical question
- **plan**: Present a structured remediation plan for approval
- **complete**: Goal achieved - include summary
- **failed**: Goal cannot be achieved - explain why

## Available Tools:
### Troubleshooting Module
- get_alert_details: Fetch full labels, fingerprints, and metadata
- get_recent_changes: Correlate incidents with deployments
- get_correlated_alerts: Find related alerts in the same group
- get_service_dependencies: Map upstream/downstream services
- get_feedback_history: Review past human feedback on similar alerts
- suggest_ssh_command: Propose server actions with safety validation

### Knowledge Module
- search_knowledge: Search runbooks and SOPs
- get_similar_incidents: Find historical parallels using vector search
- get_runbook: Retrieve specific remediation steps
- get_proven_solutions: Access learning library of successful fixes

### Observability Module
- query_grafana_metrics: Query Prometheus using PromQL
- query_grafana_logs: Search Loki using LogQL
- get_active_alerts: Query active alerts database

## Thinking Guidelines
Your "thinking" field should show your reasoning process:
- What you understand about the current situation
- What evidence you've gathered so far
- Your hypothesis based on the evidence
- Why you're choosing this particular action
- What you expect to learn from this step

## Rules:
1. ALWAYS include the "phase" field matching your current IVIPA phase
2. ALWAYS include detailed "thinking" - this builds user trust
3. In INVESTIGATE phase, you MUST call at least 2 tools before moving to PLAN
4. Never skip phases - follow IDENTIFY → VERIFY → INVESTIGATE → PLAN → ACT
5. If a command fails, analyze the error and try an alternative approach
6. Use "question" only when you absolutely need user input

## Safety:
- All commands are validated by Safety Validator before execution
- Prefer read-only investigation before making changes
- Always backup before modifying critical files
- Destructive commands require explicit user confirmation
"""


def get_agent_system_prompt(
    goal: str,
    alert: Optional[Alert] = None,
    current_phase: str = IVIPAPhase.IDENTIFY.value,
    investigation_count: int = 0,
    task_list: Optional[List[dict]] = None
) -> str:
    """Build the complete system prompt with goal, alert context, and IVIPA state."""
    prompt = AGENT_SYSTEM_PROMPT

    # Add current IVIPA phase status
    prompt += f"""

## CURRENT IVIPA STATUS:
- Current Phase: {current_phase.upper()}
- Investigation Tools Called: {investigation_count} (minimum required: {MIN_INVESTIGATION_TOOLS})
"""

    if current_phase == IVIPAPhase.INVESTIGATE.value and investigation_count < MIN_INVESTIGATION_TOOLS:
        prompt += f"⚠️ You need {MIN_INVESTIGATION_TOOLS - investigation_count} more investigation step(s) before moving to PLAN phase.\n"

    prompt += f"\n## GOAL:\n{goal}\n"

    if alert:
        prompt += f"""
## ALERT_CONTEXT:
- Alert Name: {alert.alert_name}
- Severity: {alert.severity}
- Instance: {alert.instance}
- Status: {alert.status}
- Summary: {alert.annotations_json.get('summary', 'N/A')}
- Description: {alert.annotations_json.get('description', 'N/A')}
- Labels: {json.dumps(alert.labels_json) if alert.labels_json else 'N/A'}
- Fingerprint: {alert.fingerprint or 'N/A'}

## INITIAL ANALYSIS:
{alert.ai_analysis or 'No prior analysis available.'}
"""

    # Add task list if present
    if task_list:
        prompt += "\n## CURRENT TASK LIST:\n"
        for task in task_list:
            status_icon = "✓" if task.get("status") == "completed" else "○"
            prompt += f"- [{status_icon}] {task.get('description', 'Unknown task')}\n"

    return prompt


def parse_agent_response(response_text: str) -> Dict[str, Any]:
    """
    Parse the agent's JSON response with IVIPA workflow support.

    Returns:
        dict with keys: phase, thinking, action, tool_name, content, reasoning

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
        # Try to find JSON object with either "action" or "phase" key
        json_match = re.search(r'\{[^{}]*(?:"action"|"phase")[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            # Try to find any JSON object
            json_match = re.search(r'\{[\s\S]*\}', response_text, re.DOTALL)
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
    valid_actions = ['command', 'tool_call', 'question', 'plan', 'complete', 'failed']
    if action not in valid_actions:
        raise ValueError(f"Invalid action: {action}. Must be one of {valid_actions}")

    # Extract phase (default to 'identify' for backward compatibility)
    phase = data.get('phase', 'identify').lower()
    valid_phases = ['identify', 'verify', 'investigate', 'plan', 'act', 'complete']
    if phase not in valid_phases:
        phase = 'identify'  # Default fallback

    # Extract thinking (visible reasoning)
    thinking = data.get('thinking', '')

    # Extract tool_name for tool_call actions
    tool_name = data.get('tool_name', '') if action == 'tool_call' else ''

    return {
        'phase': phase,
        'thinking': thinking,
        'action': action,
        'tool_name': tool_name,
        'content': data.get('content', ''),
        'reasoning': data.get('reasoning', '')
    }


class AgentService:
    """
    Orchestrates the autonomous agent troubleshooting loop.

    Enhanced with IVIPA workflow support:
    - Visible thinking at each phase
    - Phase tracking and enforcement
    - Investigation policy (min 2 tools before planning)
    - Plan mode with approval
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

    # ==================== IVIPA Phase Management ====================

    async def update_phase(self, session: AgentSession, new_phase: IVIPAPhase):
        """Update the current IVIPA phase with history tracking."""
        old_phase = session.current_phase

        # Track phase transition
        if session.phase_history is None:
            session.phase_history = []

        session.phase_history.append({
            "from": old_phase,
            "to": new_phase.value,
            "timestamp": datetime.utcnow().isoformat(),
            "step_number": session.current_step_number
        })

        session.current_phase = new_phase.value
        session.updated_at = datetime.utcnow()
        self.db.commit()

        await self.notify("phase_changed", {
            "session_id": str(session.id),
            "old_phase": old_phase,
            "new_phase": new_phase.value,
            "investigation_count": session.investigation_tool_count
        })

        logger.info(f"Agent phase transition: {old_phase} → {new_phase.value}")

    def can_transition_to_plan(self, session: AgentSession) -> bool:
        """Check if the agent has completed enough investigation to move to PLAN phase."""
        return session.investigation_tool_count >= MIN_INVESTIGATION_TOOLS

    async def increment_investigation_count(self, session: AgentSession):
        """Increment the investigation tool count and notify frontend."""
        session.investigation_tool_count = (session.investigation_tool_count or 0) + 1
        self.db.commit()
        logger.debug(f"Investigation count: {session.investigation_tool_count}/{MIN_INVESTIGATION_TOOLS}")

        # Notify frontend of investigation count update
        await self.notify("investigation_update", {
            "session_id": str(session.id),
            "count": session.investigation_tool_count,
            "required": MIN_INVESTIGATION_TOOLS,
            "can_plan": session.investigation_tool_count >= MIN_INVESTIGATION_TOOLS
        })

    def get_next_phase(self, current_phase: str, action: Dict[str, Any], session: AgentSession) -> str:
        """Determine the next IVIPA phase based on current state and action."""
        requested_phase = action.get('phase', current_phase)

        # Phase transition rules
        phase_order = ['identify', 'verify', 'investigate', 'plan', 'act', 'complete']

        current_idx = phase_order.index(current_phase) if current_phase in phase_order else 0
        requested_idx = phase_order.index(requested_phase) if requested_phase in phase_order else current_idx

        # Don't allow skipping phases (except for investigation policy)
        if requested_idx > current_idx + 1:
            # Allow jumping to next phase only
            return phase_order[min(current_idx + 1, len(phase_order) - 1)]

        # Enforce investigation policy
        if requested_phase == 'plan' and not self.can_transition_to_plan(session):
            logger.warning(f"Cannot transition to PLAN: only {session.investigation_tool_count}/{MIN_INVESTIGATION_TOOLS} investigation steps completed")
            return 'investigate'

        return requested_phase

    # ==================== Task List Management ====================

    def add_task(self, session: AgentSession, description: str, phase: str):
        """Add a task to the session's task list."""
        if session.task_list is None:
            session.task_list = []

        task = {
            "id": len(session.task_list) + 1,
            "description": description,
            "status": "pending",
            "phase": phase,
            "created_at": datetime.utcnow().isoformat()
        }
        session.task_list.append(task)
        self.db.commit()
        return task

    def complete_task(self, session: AgentSession, task_id: int):
        """Mark a task as completed."""
        if session.task_list:
            for task in session.task_list:
                if task.get("id") == task_id:
                    task["status"] = "completed"
                    task["completed_at"] = datetime.utcnow().isoformat()
                    self.db.commit()
                    return task
        return None
    
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
        Call LLM to determine next action with IVIPA workflow support.

        Returns:
            dict with keys: phase, thinking, action, tool_name, content, reasoning
        """
        await self.update_status(session, AgentStatus.THINKING)

        # Notify frontend that thinking has started
        await self.notify("thinking_started", {
            "session_id": str(session.id),
            "current_phase": session.current_phase,
            "step_number": session.current_step_number + 1
        })

        # Get alert context if available
        chat_session = session.chat_session
        alert = chat_session.alert if chat_session else None

        # Build system prompt with IVIPA state
        system_prompt = get_agent_system_prompt(
            goal=session.goal,
            alert=alert,
            current_phase=session.current_phase or IVIPAPhase.IDENTIFY.value,
            investigation_count=session.investigation_tool_count or 0,
            task_list=session.task_list
        )

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
        """Create a new agent step from the LLM action with IVIPA support."""
        session.current_step_number += 1

        # Determine the actual phase (with policy enforcement)
        requested_phase = action.get('phase', session.current_phase)
        actual_phase = self.get_next_phase(session.current_phase, action, session)

        # Update session phase if it changed
        if actual_phase != session.current_phase:
            await self.update_phase(session, IVIPAPhase(actual_phase))

        # Track investigation tools
        if actual_phase == IVIPAPhase.INVESTIGATE.value and action['action'] in ['command', 'tool_call']:
            await self.increment_investigation_count(session)

        step = AgentStep(
            agent_session_id=session.id,
            step_number=session.current_step_number,
            ivipa_phase=actual_phase,
            step_type=action['action'],
            content=action['content'],
            thinking=action.get('thinking', ''),  # Visible thinking
            reasoning=action.get('reasoning', ''),
            tool_name=action.get('tool_name', ''),
            status=StepStatus.PENDING.value
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)

        # Send notification with thinking included
        await self.notify("step_created", {
            "session_id": str(session.id),
            "step": {
                "id": str(step.id),
                "step_number": step.step_number,
                "ivipa_phase": step.ivipa_phase,
                "step_type": step.step_type,
                "content": step.content,
                "thinking": step.thinking,
                "reasoning": step.reasoning,
                "tool_name": step.tool_name,
                "status": step.status
            }
        })

        return step
    
    async def execute_command(
        self,
        session: AgentSession,
        step: AgentStep,
        ssh_client: SSHClient
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
            if not ssh_client.conn:
                await ssh_client.connect()
            
            # Run command
            result = await ssh_client.conn.run(command, check=False, timeout=60)
            
            output = result.stdout or ""
            if result.stderr:
                output += f"\n[STDERR]: {result.stderr}"
            
            exit_code = result.exit_status
            
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
        ssh_client: SSHClient
    ) -> AsyncGenerator[dict, None]:
        """
        Main agent loop with IVIPA workflow support.

        Runs until complete, failed, or stopped.
        Yields events for each step including thinking phases.
        Enforces IVIPA phase transitions and investigation policy.
        """
        logger.info(f"Starting IVIPA agent loop for session {session.id}")
        logger.info(f"Initial phase: {session.current_phase}")
        
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
                logger.info(f"Agent action: {action['action']} (phase: {action.get('phase', 'unknown')}) - {action['content'][:50]}...")

                # 2. Create step (this also handles phase tracking)
                step = await self.create_step(session, action)

                # 3. Send and yield thinking event if thinking is present
                if action.get('thinking'):
                    # Notify frontend of thinking block
                    await self.notify("thinking", {
                        "session_id": str(session.id),
                        "step_number": step.step_number,
                        "phase": action.get('phase', session.current_phase),
                        "thinking": action['thinking']
                    })

                    yield {
                        "type": "thinking",
                        "step": step,
                        "phase": action.get('phase', session.current_phase),
                        "thinking": action['thinking']
                    }

                # 4. Handle action type
                if action['action'] == 'command':
                    # Check if approval is needed
                    if not session.auto_approve:
                        await self.update_status(session, AgentStatus.AWAITING_APPROVAL)

                        yield {
                            "type": "awaiting_approval",
                            "step": step,
                            "phase": step.ivipa_phase
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
                                    session, step, ssh_client
                                )
                                yield {
                                    "type": "executed",
                                    "step": step,
                                    "phase": step.ivipa_phase,
                                    "output": output,
                                    "exit_code": exit_code
                                }
                                break

                            elif step.status == StepStatus.REJECTED.value:
                                # Skip this step
                                yield {
                                    "type": "rejected",
                                    "step": step,
                                    "phase": step.ivipa_phase
                                }
                                break
                    else:
                        # Auto-approve mode - execute immediately
                        output, exit_code = await self.execute_command(
                            session, step, ssh_client
                        )
                        yield {
                            "type": "executed",
                            "step": step,
                            "phase": step.ivipa_phase,
                            "output": output,
                            "exit_code": exit_code
                        }

                elif action['action'] == 'tool_call':
                    # Handle tool calls (for future tool framework)
                    # For now, treat tool_call similar to command but mark it
                    tool_name = action.get('tool_name', 'unknown')
                    logger.info(f"Tool call: {tool_name}")

                    # Yield tool call event
                    yield {
                        "type": "tool_call",
                        "step": step,
                        "phase": step.ivipa_phase,
                        "tool_name": tool_name,
                        "content": action['content']
                    }

                    # TODO: Implement actual tool execution when tool framework is ready
                    # For now, mark as executed with placeholder
                    step.status = StepStatus.EXECUTED.value
                    step.output = f"[Tool '{tool_name}' called - tool framework pending implementation]"
                    self.db.commit()

                    await self.notify("step_updated", {
                        "session_id": str(session.id),
                        "step": {
                            "id": str(step.id),
                            "status": step.status,
                            "output": step.output
                        }
                    })

                elif action['action'] == 'plan':
                    # Handle plan action - present plan for approval
                    logger.info(f"Plan proposed: {action['content'][:100]}...")

                    # Store plan in session
                    session.current_plan = {
                        "content": action['content'],
                        "created_at": datetime.utcnow().isoformat(),
                        "status": "pending_approval"
                    }
                    self.db.commit()

                    await self.update_status(session, AgentStatus.AWAITING_APPROVAL)

                    yield {
                        "type": "plan_proposed",
                        "step": step,
                        "phase": step.ivipa_phase,
                        "plan": action['content'],
                        "thinking": action.get('thinking', '')
                    }

                    # Wait for plan approval
                    while True:
                        await asyncio.sleep(0.5)
                        self.db.refresh(session)
                        self.db.refresh(step)

                        if session.status == AgentStatus.STOPPED.value:
                            break

                        if step.status == StepStatus.APPROVED.value:
                            # Plan approved - move to ACT phase
                            session.current_plan["status"] = "approved"
                            self.db.commit()

                            await self.update_phase(session, IVIPAPhase.ACT)

                            yield {
                                "type": "plan_approved",
                                "step": step,
                                "phase": "act"
                            }
                            break

                        elif step.status == StepStatus.REJECTED.value:
                            # Plan rejected - go back to investigate
                            session.current_plan["status"] = "rejected"
                            self.db.commit()

                            yield {
                                "type": "plan_rejected",
                                "step": step,
                                "phase": step.ivipa_phase
                            }
                            break

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
