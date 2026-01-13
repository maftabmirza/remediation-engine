"""
Agent API Router

Provides API endpoints for AI Agent Mode - autonomous goal-driven SSH execution.
"""
import asyncio
import logging
import json
from typing import Dict, Optional, Set
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState

from app.database import get_db
from app.models import User, LLMProvider, ServerCredential
from app.models_agent import AgentSession, AgentStep
from app.models_revive import AISession
from app.services.auth_service import get_current_user, get_current_user_ws
from app.services.ssh_service import get_ssh_connection
from app.services.llm_service import get_api_key_for_provider
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["agent"])
# Separate router for WebSocket (no prefix) to match frontend expectation /ws/agent/{id}
ws_router = APIRouter(tags=["agent"])
settings = get_settings()


# ============= Schemas =============

class AgentStartRequest(BaseModel):
    """Request to start a new agent session"""
    chat_session_id: Optional[str] = None
    server_id: str
    goal: str
    auto_approve: bool = False
    max_steps: int = 20


class AgentStepResponse(BaseModel):
    """Response for an agent step"""
    id: str
    step_number: int
    step_type: str
    content: str
    reasoning: Optional[str] = None
    output: Optional[str] = None
    exit_code: Optional[int] = None
    status: str


class AgentSessionResponse(BaseModel):
    """Response for an agent session"""
    id: str
    goal: str
    status: str
    current_step_number: int
    max_steps: int
    auto_approve: bool


# ============= Active Session Management =============

# Track active WebSocket connections per agent session
active_connections: Dict[UUID, Set[WebSocket]] = {}
# Track agent execution tasks
agent_tasks: Dict[UUID, asyncio.Task] = {}


async def broadcast_to_session(session_id: UUID, message: dict):
    """Broadcast a message to all WebSocket connections for a session"""
    if session_id in active_connections:
        dead_connections = set()
        for ws in active_connections[session_id]:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(message)
                else:
                    dead_connections.add(ws)
            except Exception as e:
                logger.debug(f"Failed to broadcast: {e}")
                dead_connections.add(ws)
        # Clean up dead connections
        for ws in dead_connections:
            active_connections[session_id].discard(ws)


# ============= REST API Endpoints =============

@router.post("/start")
async def start_agent(
    request: AgentStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a new agent session.
    
    Creates an agent session that will work towards the specified goal
    by executing commands on the target server.
    """
    # Validate server exists
    try:
        server_uuid = UUID(request.server_id)
        server = db.query(ServerCredential).filter(ServerCredential.id == server_uuid).first()
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid server ID")
    
    # Optionally link to chat session
    chat_session_id = None
    if request.chat_session_id:
        try:
            chat_session_id = UUID(request.chat_session_id)
        except ValueError:
            pass  # Not a valid UUID, ignore
    
    # Create agent session
    session_id = uuid4()
    agent_session = AgentSession(
        id=session_id,
        chat_session_id=chat_session_id,
        user_id=current_user.id,
        server_id=server_uuid,
        goal=request.goal,
        status='idle',
        auto_approve=request.auto_approve,
        max_steps=request.max_steps,
        current_step_number=0
    )
    
    db.add(agent_session)
    db.commit()
    db.refresh(agent_session)
    
    logger.info(f"Agent session created: {session_id} for goal: {request.goal[:50]}...")
    
    return {
        "id": str(session_id),
        "goal": request.goal,
        "status": "idle",
        "current_step_number": 0,
        "max_steps": request.max_steps,
        "auto_approve": request.auto_approve,
        "server_name": server.name
    }


@router.post("/{session_id}/approve")
async def approve_step(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Approve the pending step in an agent session"""
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    
    session = db.query(AgentSession).filter(
        AgentSession.id == session_uuid,
        AgentSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Find the pending step
    pending_step = db.query(AgentStep).filter(
        AgentStep.agent_session_id == session_uuid,
        AgentStep.status == 'pending'
    ).order_by(AgentStep.step_number.desc()).first()
    
    if not pending_step:
        raise HTTPException(status_code=400, detail="No pending step to approve")
    
    # Broadcast approval
    await broadcast_to_session(session_uuid, {
        "type": "approval_received",
        "step_id": str(pending_step.id),
        "approved": True
    })
    
    return {"success": True, "step_id": str(pending_step.id)}


@router.post("/{session_id}/reject")
async def reject_step(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reject/skip the pending step in an agent session"""
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    
    session = db.query(AgentSession).filter(
        AgentSession.id == session_uuid,
        AgentSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Find the pending step
    pending_step = db.query(AgentStep).filter(
        AgentStep.agent_session_id == session_uuid,
        AgentStep.status == 'pending'
    ).order_by(AgentStep.step_number.desc()).first()
    
    if not pending_step:
        raise HTTPException(status_code=400, detail="No pending step to reject")
    
    # Mark as rejected
    pending_step.status = 'rejected'
    db.commit()
    
    # Broadcast rejection
    await broadcast_to_session(session_uuid, {
        "type": "approval_received",
        "step_id": str(pending_step.id),
        "approved": False
    })
    
    return {"success": True, "step_id": str(pending_step.id)}


@router.post("/{session_id}/stop")
async def stop_agent(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stop an agent session"""
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    
    session = db.query(AgentSession).filter(
        AgentSession.id == session_uuid,
        AgentSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Cancel running task if any
    if session_uuid in agent_tasks:
        task = agent_tasks[session_uuid]
        if not task.done():
            task.cancel()
        del agent_tasks[session_uuid]
    
    # Update session status
    session.status = 'stopped'
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    
    # Broadcast stop
    await broadcast_to_session(session_uuid, {
        "type": "complete",
        "status": "stopped",
        "message": "Agent stopped by user"
    })
    
    logger.info(f"Agent session stopped: {session_id}")
    
    return {"success": True, "status": "stopped"}


@router.post("/{session_id}/answer")
async def answer_agent_question(
    session_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Answer a question from the agent"""
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    
    session = db.query(AgentSession).filter(
        AgentSession.id == session_uuid,
        AgentSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    answer = payload.get("answer", "")
    
    # Broadcast answer
    await broadcast_to_session(session_uuid, {
        "type": "user_answer",
        "answer": answer
    })
    
    return {"success": True}


# ============= WebSocket Endpoint =============

@ws_router.websocket("/ws/agent/{session_id}")
async def agent_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time agent communication.
    
    Handles:
    - Sending step updates to the client
    - Receiving approval/rejection/stop commands
    - Running the agent execution loop
    """
    # Authenticate
    user = await get_current_user_ws(token, db)
    if not user:
        await websocket.close(code=4001)
        return
    
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        await websocket.close(code=4004)
        return
    
    # Verify session ownership
    session = db.query(AgentSession).filter(
        AgentSession.id == session_uuid,
        AgentSession.user_id == user.id
    ).first()
    
    if not session:
        await websocket.close(code=4004)
        return
    
    await websocket.accept()
    logger.info(f"Agent WebSocket connected: session={session_id}, user={user.username}")
    
    # Register connection
    if session_uuid not in active_connections:
        active_connections[session_uuid] = set()
    active_connections[session_uuid].add(websocket)
    
    # Send connected message
    await websocket.send_json({"type": "connected", "session_id": session_id})
    
    # Create event for signaling between tasks
    approval_event = asyncio.Event()
    approval_result = {"approved": False, "answer": None}
    stop_requested = False
    
    async def handle_messages():
        """Handle incoming WebSocket messages"""
        nonlocal approval_result, stop_requested
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    msg_type = msg.get("type")
                    
                    if msg_type == "approve":
                        approval_result["approved"] = True
                        approval_event.set()
                    elif msg_type == "reject":
                        approval_result["approved"] = False
                        approval_event.set()
                    elif msg_type == "stop":
                        stop_requested = True
                        approval_event.set()  # Wake up any waiting
                    elif msg_type == "answer":
                        approval_result["answer"] = msg.get("answer", "")
                        approval_event.set()
                        
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            logger.debug(f"Agent WebSocket disconnected: {session_id}")
        except Exception as e:
            logger.debug(f"Message handler error: {e}")
    
    async def run_agent():
        """Run the agent execution loop"""
        nonlocal stop_requested
        
        from litellm import acompletion
        
        # Get default LLM provider
        provider = db.query(LLMProvider).filter(
            LLMProvider.is_default == True,
            LLMProvider.is_enabled == True
        ).first()
        
        if not provider:
            await websocket.send_json({
                "type": "error",
                "message": "No LLM provider configured"
            })
            return
        
        # Get SSH connection
        try:
            ssh_client = await get_ssh_connection(db, session.server_id)
            await ssh_client.connect()
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"SSH connection failed: {str(e)}"
            })
            return
        
        try:
            # Update session status
            session.status = 'thinking'
            db.commit()
            await websocket.send_json({"type": "status_changed", "status": "thinking"})
            
            # Build system prompt
            server = db.query(ServerCredential).filter(ServerCredential.id == session.server_id).first()
            system_prompt = f"""You are an AI agent helping to accomplish tasks on a Linux server.

Server: {server.name} ({server.hostname})
Goal: {session.goal}

You will work step by step to accomplish this goal. For each step:
1. Think about what command to run next
2. Explain your reasoning briefly
3. Provide the exact command to execute

Respond in JSON format:
{{"step_type": "command", "command": "your command here", "reasoning": "why this command"}}

When the goal is complete:
{{"step_type": "complete", "summary": "what was accomplished"}}

If you encounter an unrecoverable error:
{{"step_type": "failed", "reason": "what went wrong"}}

If you need information from the user:
{{"step_type": "question", "question": "your question"}}

Important rules:
- Always use non-interactive commands (add -y for apt, etc.)
- Check command results before proceeding
- Maximum {session.max_steps} steps allowed
- Current step: {session.current_step_number}"""

            messages = [{"role": "system", "content": system_prompt}]
            
            # Run agent loop
            while session.current_step_number < session.max_steps and not stop_requested:
                # Refresh session from DB
                db.refresh(session)
                
                if session.status == 'stopped':
                    break
                
                # Get next action from LLM
                try:
                    api_key = get_api_key_for_provider(provider.provider_type)
                    model = f"{provider.provider_type}/{provider.model_id}"
                    
                    response = await acompletion(
                        model=model,
                        messages=messages,
                        api_key=api_key,
                        temperature=0.3,
                        max_tokens=1000
                    )
                    
                    assistant_message = response.choices[0].message.content
                    messages.append({"role": "assistant", "content": assistant_message})
                    
                except Exception as e:
                    logger.error(f"LLM error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"LLM error: {str(e)}"
                    })
                    break
                
                # Parse the response
                try:
                    # Extract JSON from response
                    json_match = assistant_message
                    if "```json" in assistant_message:
                        json_match = assistant_message.split("```json")[1].split("```")[0]
                    elif "```" in assistant_message:
                        json_match = assistant_message.split("```")[1].split("```")[0]
                    
                    action = json.loads(json_match.strip())
                except (json.JSONDecodeError, IndexError) as e:
                    logger.warning(f"Failed to parse agent response: {e}")
                    # Ask LLM to retry with proper format
                    messages.append({
                        "role": "user", 
                        "content": "Please respond with valid JSON in the format specified."
                    })
                    continue
                
                step_type = action.get("step_type", "command")
                
                # Handle completion
                if step_type == "complete":
                    session.status = 'completed'
                    session.completed_at = datetime.now(timezone.utc)
                    session.summary = action.get("summary", "Goal completed")
                    db.commit()
                    
                    # Create final step
                    step = AgentStep(
                        id=uuid4(),
                        agent_session_id=session.id,
                        step_number=session.current_step_number + 1,
                        step_type='complete',
                        content=action.get("summary", "Goal completed"),
                        status='executed'
                    )
                    db.add(step)
                    db.commit()
                    
                    await websocket.send_json({
                        "type": "step_created",
                        "step": {
                            "id": str(step.id),
                            "step_number": step.step_number,
                            "step_type": "complete",
                            "content": step.content,
                            "status": "executed"
                        }
                    })
                    
                    await websocket.send_json({
                        "type": "complete",
                        "status": "completed",
                        "message": action.get("summary", "Goal completed")
                    })
                    break
                
                # Handle failure
                elif step_type == "failed":
                    session.status = 'failed'
                    session.completed_at = datetime.now(timezone.utc)
                    session.error_message = action.get("reason", "Unknown error")
                    db.commit()
                    
                    step = AgentStep(
                        id=uuid4(),
                        agent_session_id=session.id,
                        step_number=session.current_step_number + 1,
                        step_type='failed',
                        content=action.get("reason", "Unknown error"),
                        status='failed'
                    )
                    db.add(step)
                    db.commit()
                    
                    await websocket.send_json({
                        "type": "step_created",
                        "step": {
                            "id": str(step.id),
                            "step_number": step.step_number,
                            "step_type": "failed",
                            "content": step.content,
                            "status": "failed"
                        }
                    })
                    
                    await websocket.send_json({
                        "type": "complete",
                        "status": "failed",
                        "message": action.get("reason", "Unknown error")
                    })
                    break
                
                # Handle question
                elif step_type == "question":
                    session.status = 'awaiting_input'
                    db.commit()
                    
                    step = AgentStep(
                        id=uuid4(),
                        agent_session_id=session.id,
                        step_number=session.current_step_number + 1,
                        step_type='question',
                        content=action.get("question", ""),
                        status='pending'
                    )
                    db.add(step)
                    session.current_step_number += 1
                    db.commit()
                    
                    await websocket.send_json({
                        "type": "step_created",
                        "step": {
                            "id": str(step.id),
                            "step_number": step.step_number,
                            "step_type": "question",
                            "content": step.content,
                            "status": "pending"
                        }
                    })
                    
                    # Wait for answer
                    approval_event.clear()
                    await approval_event.wait()
                    
                    if stop_requested:
                        break
                    
                    answer = approval_result.get("answer", "")
                    step.output = answer
                    step.status = 'executed'
                    db.commit()
                    
                    messages.append({"role": "user", "content": f"User answer: {answer}"})
                    continue
                
                # Handle command
                else:
                    command = action.get("command", "")
                    reasoning = action.get("reasoning", "")
                    
                    if not command:
                        messages.append({
                            "role": "user",
                            "content": "Please provide a command to execute."
                        })
                        continue
                    
                    # Create step
                    step = AgentStep(
                        id=uuid4(),
                        agent_session_id=session.id,
                        step_number=session.current_step_number + 1,
                        step_type='command',
                        content=command,
                        reasoning=reasoning,
                        status='pending'
                    )
                    db.add(step)
                    session.current_step_number += 1
                    db.commit()
                    
                    await websocket.send_json({
                        "type": "step_created",
                        "step": {
                            "id": str(step.id),
                            "step_number": step.step_number,
                            "step_type": "command",
                            "content": command,
                            "reasoning": reasoning,
                            "status": "pending"
                        }
                    })
                    
                    # Check if auto-approve or wait for approval
                    if not session.auto_approve:
                        session.status = 'awaiting_approval'
                        db.commit()
                        await websocket.send_json({"type": "status_changed", "status": "awaiting_approval"})
                        
                        # Wait for approval
                        approval_event.clear()
                        await approval_event.wait()
                        
                        if stop_requested:
                            break
                        
                        if not approval_result.get("approved", False):
                            step.status = 'rejected'
                            db.commit()
                            
                            await websocket.send_json({
                                "type": "step_updated",
                                "step": {
                                    "id": str(step.id),
                                    "status": "rejected"
                                }
                            })
                            
                            # Tell LLM the command was skipped
                            messages.append({
                                "role": "user",
                                "content": "User skipped this command. Try a different approach."
                            })
                            
                            session.status = 'thinking'
                            db.commit()
                            await websocket.send_json({"type": "status_changed", "status": "thinking"})
                            continue
                    
                    # Execute command
                    session.status = 'executing'
                    db.commit()
                    await websocket.send_json({"type": "status_changed", "status": "executing"})
                    
                    try:
                        # Run command via SSH
                        result = await ssh_client.conn.run(command, timeout=120)
                        output = result.stdout + result.stderr
                        exit_code = result.exit_status
                        
                        step.output = output[:50000]  # Limit output size
                        step.exit_code = exit_code
                        step.status = 'executed'
                        step.executed_at = datetime.now(timezone.utc)
                        db.commit()
                        
                        await websocket.send_json({
                            "type": "step_updated",
                            "step": {
                                "id": str(step.id),
                                "output": output[:5000],  # Limit for WS
                                "exit_code": exit_code,
                                "status": "executed"
                            }
                        })
                        
                        # Add result to conversation
                        messages.append({
                            "role": "user",
                            "content": f"Command output (exit code {exit_code}):\n{output[:10000]}"
                        })
                        
                    except asyncio.TimeoutError:
                        step.output = "Command timed out after 120 seconds"
                        step.exit_code = -1
                        step.status = 'failed'
                        db.commit()
                        
                        await websocket.send_json({
                            "type": "step_updated",
                            "step": {
                                "id": str(step.id),
                                "output": "Command timed out",
                                "exit_code": -1,
                                "status": "failed"
                            }
                        })
                        
                        messages.append({
                            "role": "user",
                            "content": "Command timed out after 120 seconds."
                        })
                        
                    except Exception as e:
                        logger.error(f"Command execution error: {e}")
                        step.output = str(e)
                        step.exit_code = -1
                        step.status = 'failed'
                        db.commit()
                        
                        await websocket.send_json({
                            "type": "step_updated",
                            "step": {
                                "id": str(step.id),
                                "output": str(e),
                                "exit_code": -1,
                                "status": "failed"
                            }
                        })
                        
                        messages.append({
                            "role": "user",
                            "content": f"Command failed with error: {str(e)}"
                        })
                    
                    session.status = 'thinking'
                    db.commit()
                    await websocket.send_json({"type": "status_changed", "status": "thinking"})
            
            # Check if we hit max steps
            if session.current_step_number >= session.max_steps and session.status not in ('completed', 'failed', 'stopped'):
                session.status = 'failed'
                session.completed_at = datetime.now(timezone.utc)
                session.error_message = "Maximum steps reached"
                db.commit()
                
                await websocket.send_json({
                    "type": "complete",
                    "status": "failed",
                    "message": "Maximum steps reached without completing goal"
                })
                
        finally:
            # Close SSH connection
            try:
                await ssh_client.close()
            except Exception:
                pass
    
    # Run both tasks
    message_task = asyncio.create_task(handle_messages())
    agent_task = asyncio.create_task(run_agent())
    
    # Store task for potential cancellation
    agent_tasks[session_uuid] = agent_task
    
    try:
        # Wait for either task to complete
        done, pending = await asyncio.wait(
            [message_task, agent_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
    except Exception as e:
        logger.error(f"Agent WebSocket error: {e}")
    finally:
        # Cleanup
        if session_uuid in active_connections:
            active_connections[session_uuid].discard(websocket)
            if not active_connections[session_uuid]:
                del active_connections[session_uuid]
        
        if session_uuid in agent_tasks:
            del agent_tasks[session_uuid]
        
        logger.info(f"Agent WebSocket closed: session={session_id}")
