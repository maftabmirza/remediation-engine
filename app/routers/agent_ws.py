"""
Agent WebSocket endpoint for real-time updates.
"""
import asyncio
import json
import logging
from uuid import UUID
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState

from app.database import get_db
from app.models import User, LLMProvider
from app.models_agent import AgentSession, AgentStatus
from app.services.auth_service import get_current_user_ws
from app.services.agent_service import AgentService
from app.services.executor_factory import ExecutorFactory
from app.models import ServerCredential

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Agent"])

# WebSocket close codes
WS_CLOSE_AUTH_FAILED = 4001
WS_CLOSE_SESSION_NOT_FOUND = 4004
WS_CLOSE_NO_PROVIDER = 4010
WS_CLOSE_CONNECTION_FAILED = 4011
WS_CLOSE_INTERNAL_ERROR = 4500

# Track active connections per session
active_connections: Dict[UUID, Set[WebSocket]] = {}


async def safe_send(websocket: WebSocket, message: dict) -> bool:
    """Safely send a JSON message to WebSocket."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_json(message)
            return True
    except Exception as e:
        logger.debug(f"Failed to send WebSocket message: {e}")
    return False


async def safe_close(websocket: WebSocket, code: int = 1000) -> None:
    """Safely close a WebSocket connection."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=code)
    except Exception as e:
        logger.debug(f"Error closing WebSocket: {e}")


async def broadcast_to_session(session_id: UUID, message: dict):
    """Broadcast a message to all clients connected to a session."""
    if session_id in active_connections:
        disconnected = set()
        for ws in active_connections[session_id]:
            if not await safe_send(ws, message):
                disconnected.add(ws)
        # Clean up disconnected clients
        active_connections[session_id] -= disconnected


@router.websocket("/ws/agent/{session_id}")
async def agent_websocket(
    websocket: WebSocket,
    session_id: UUID,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time agent updates.
    
    Message types sent to client:
    - status_changed: Agent status changed
    - step_created: New step created
    - step_updated: Step executed/completed
    - thinking: Agent is generating next action
    - complete: Agent finished (completed/failed/stopped)
    - error: An error occurred
    
    Close codes:
    - 4001: Authentication failed
    - 4004: Session not found
    - 4010: No LLM provider configured
    - 4011: SSH connection failed
    - 4500: Internal server error
    """
    # Authenticate
    user = await get_current_user_ws(token, db)
    if not user:
        logger.warning(f"Agent WebSocket auth failed for session {session_id}")
        await websocket.close(code=WS_CLOSE_AUTH_FAILED)
        return

    await websocket.accept()
    logger.info(f"Agent WebSocket connected: user={user.username}, session={session_id}")
    
    # Verify session ownership
    session = db.query(AgentSession).filter(
        AgentSession.id == session_id,
        AgentSession.user_id == user.id
    ).first()
    
    if not session:
        logger.warning(f"Agent session not found: {session_id}")
        await safe_send(websocket, {"type": "error", "message": "Session not found"})
        await safe_close(websocket, WS_CLOSE_SESSION_NOT_FOUND)
        return
    
    # Get LLM provider
    chat_session = session.chat_session
    provider = chat_session.llm_provider if chat_session else None
    
    if not provider:
        # Fallback to default
        provider = db.query(LLMProvider).filter(
            LLMProvider.is_default == True,
            LLMProvider.is_enabled == True
        ).first()
    
    if not provider:
        logger.error(f"No LLM provider for agent session {session_id}")
        await safe_send(websocket, {"type": "error", "message": "No LLM provider configured"})
        await safe_close(websocket, WS_CLOSE_NO_PROVIDER)
        return
    
    # Track this connection
    if session_id not in active_connections:
        active_connections[session_id] = set()
    active_connections[session_id].add(websocket)
    
    # Create executor connection (SSH or WinRM based on server protocol)
    executor = None
    try:
        if session.server_id:
            server = db.query(ServerCredential).filter(ServerCredential.id == session.server_id).first()
            if not server:
                await safe_send(websocket, {"type": "error", "message": "Server not found"})
                await safe_close(websocket, WS_CLOSE_CONNECTION_FAILED)
                return
            
            executor = ExecutorFactory.get_executor(server)
            await executor.connect()
            protocol = getattr(server, 'protocol', 'ssh')
            logger.info(f"Executor connected ({protocol}) for agent session {session_id}")
        else:
            await safe_send(websocket, {"type": "error", "message": "No server configured"})
            await safe_close(websocket, WS_CLOSE_CONNECTION_FAILED)
            return
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        await safe_send(websocket, {"type": "error", "message": f"Connection failed: {str(e)}"})
        await safe_close(websocket, WS_CLOSE_CONNECTION_FAILED)
        return
    
    # Create agent service with notification callback
    service = AgentService(db)
    
    async def notify_callback(event_type: str, data: dict):
        """Callback to broadcast events to all connected clients."""
        await broadcast_to_session(session_id, {"type": event_type, **data})
    
    service.set_notify_callback(notify_callback)
    
    try:
        # Send initial status
        await safe_send(websocket, {
            "type": "connected",
            "session_id": str(session_id),
            "status": session.status,
            "goal": session.goal
        })
        
        # Start the agent loop in a background task
        loop_task = asyncio.create_task(
            run_agent_loop(service, session, provider, executor, websocket)
        )
        
        # Handle incoming messages (for control commands)
        try:
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    # Handle control messages
                    if message.get("type") == "ping":
                        await safe_send(websocket, {"type": "pong"})
                    
                    elif message.get("type") == "stop":
                        await service.stop_session(session)
                        break
                    
                    elif message.get("type") == "approve":
                        await service.approve_step(session)
                    
                    elif message.get("type") == "reject":
                        await service.reject_step(session)
                    
                    elif message.get("type") == "answer":
                        # Handle answer to question
                        # Find pending question step and update it
                        from app.models_agent import AgentStep, StepStatus
                        from datetime import datetime
                        
                        question_step = db.query(AgentStep).filter(
                            AgentStep.agent_session_id == session_id,
                            AgentStep.step_type == "question",
                            AgentStep.status == StepStatus.PENDING.value
                        ).first()
                        
                        if question_step:
                            question_step.output = message.get("answer", "")
                            question_step.status = StepStatus.EXECUTED.value
                            question_step.executed_at = datetime.utcnow()
                            db.commit()
                        
                except WebSocketDisconnect:
                    logger.info(f"Agent WebSocket disconnected: session={session_id}")
                    break
                except json.JSONDecodeError:
                    await safe_send(websocket, {"type": "error", "message": "Invalid JSON"})
                    
        except Exception as e:
            logger.error(f"Agent WebSocket error: {e}", exc_info=True)
        
        # Cancel the loop task if still running
        if not loop_task.done():
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass
                
    except Exception as e:
        logger.error(f"Agent WebSocket error: {e}", exc_info=True)
        await safe_send(websocket, {"type": "error", "message": str(e)})
    
    finally:
        # Clean up
        if session_id in active_connections:
            active_connections[session_id].discard(websocket)
            if not active_connections[session_id]:
                del active_connections[session_id]
        
        if executor:
            await executor.disconnect()
        
        await safe_close(websocket)
        logger.debug(f"Agent WebSocket closed: session={session_id}")


async def run_agent_loop(
    service: AgentService,
    session: AgentSession,
    provider: LLMProvider,
    executor,
    websocket: WebSocket
):
    """
    Run the agent loop and handle events.
    """
    try:
        async for event in service.run_loop(session, provider, executor):
            # Log the event
            logger.debug(f"Agent event: {event.get('type')}")
            
            # Events are already sent via the notify callback
            # This loop just drives the execution
            
            # If we're awaiting approval, the loop will pause
            # until the user sends approve/reject via WebSocket
            
    except Exception as e:
        logger.error(f"Agent loop error: {e}", exc_info=True)
        await safe_send(websocket, {
            "type": "error",
            "message": f"Agent error: {str(e)}"
        })
