"""
Troubleshooting API Router

Dedicated router for the Troubleshooting mode on the /ai page.
Uses NativeToolAgent for interactive terminal + AI conversations
with tool-calling capabilities.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, AsyncGenerator
import logging
import uuid
import json
import os
import asyncio
from pydantic import BaseModel

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models import User, LLMProvider
from app.models_revive import AISession, AIMessage

router = APIRouter(
    prefix="/api/troubleshoot",
    tags=["troubleshooting"]
)

class SwitchProviderRequest(dict):
    provider_id: str

class CommandValidateRequest(BaseModel):
    command: str
    server: str

logger = logging.getLogger(__name__)


@router.post("/chat")
async def troubleshoot_chat(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handle troubleshooting chat messages via REST API.
    
    This endpoint uses the NativeToolAgent for troubleshooting conversations
    with tool calling capabilities (run commands, analyze logs, etc.)
    
    Request body:
        message: str - The user's message
        session_id: str - Session identifier for conversation context
        terminal_context: Optional[str] - Current terminal output for context
    
    Response:
        response: str - AI response with potential [CMD_CARD] markers
        session_id: str - Session ID
        tool_calls: List[str] - Tools that were called during this turn
    """
    from app.services.agentic.native_agent import NativeToolAgent
    
    message = request.get("message", "")
    session_id = request.get("session_id", "")
    terminal_context = request.get("terminal_context", "")
    
    logger.info(f"Troubleshoot chat from {current_user.username}: {message[:100]}...")
    
    try:
        # Get the default LLM provider
        provider = db.query(LLMProvider).filter(
            LLMProvider.is_default == True,
            LLMProvider.is_enabled == True
        ).first()
        
        if not provider:
            provider = db.query(LLMProvider).filter(
                LLMProvider.is_enabled == True
            ).first()
        
        if not provider:
            return {
                "response": "No LLM provider is configured. Please configure an LLM provider in Settings.",
                "message": "No LLM provider is configured. Please configure an LLM provider in Settings.",
                "session_id": session_id,
                "mode": "troubleshoot"
            }
        
        # === SESSION PERSISTENCE: Load or create session ===
        ai_session = None
        initial_messages = []
        
        if session_id:
            try:
                session_uuid = uuid.UUID(session_id)
                ai_session = db.query(AISession).filter(AISession.id == session_uuid).first()
            except (ValueError, TypeError):
                logger.warning(f"Invalid session_id format: {session_id}")
        
        if not ai_session:
            # Create new session
            ai_session = AISession(
                user_id=current_user.id,
                pillar="troubleshooting",
                title=message[:100] if message else "Troubleshooting Session"
            )
            db.add(ai_session)
            db.commit()
            db.refresh(ai_session)
            session_id = str(ai_session.id)
            logger.info(f"Created new AI session: {session_id}")
        else:
            # Load existing messages for this session
            existing_messages = db.query(AIMessage).filter(
                AIMessage.session_id == ai_session.id
            ).order_by(AIMessage.created_at).all()
            
            for msg in existing_messages:
                initial_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            logger.info(f"Loaded {len(initial_messages)} messages from session {session_id}")
        
        # Save the user message to DB
        user_msg = AIMessage(
            session_id=ai_session.id,
            role="user",
            content=message
        )
        db.add(user_msg)
        db.commit()
        
        from app.services.agentic.tools.registry import create_troubleshooting_registry
        
        # Create the Native Tool Agent with conversation history
        agent = NativeToolAgent(
            db=db,
            provider=provider,
            alert=None,  # No specific alert context
            initial_messages=initial_messages,
            registry_factory=create_troubleshooting_registry
        )
        
        # Use stream() to get CMD_CARD markers for command buttons
        # Collect all streamed chunks into a single response
        full_response = ""
        tool_calls = []
        
        async for chunk in agent.stream(message):
            full_response += chunk
        
        # Get tool calls made
        if hasattr(agent, 'tool_calls_made'):
            tool_calls = agent.tool_calls_made
        
        # Save the assistant response to DB
        assistant_msg = AIMessage(
            session_id=ai_session.id,
            role="assistant",
            content=full_response,
            metadata_json={"tool_calls": tool_calls} if tool_calls else None
        )
        db.add(assistant_msg)
        db.commit()
        
        # Debug: Log the full response to verify CMD_CARD markers
        logger.info(f"Troubleshoot chat response length: {len(full_response)}")
        if "[CMD_CARD]" in full_response:
            logger.info("✅ CMD_CARD markers found in response")
        else:
            logger.debug("No CMD_CARD markers in response (may be expected)")
        
        return {
            "response": full_response,
            "message": full_response,
            "session_id": session_id,
            "tool_calls": tool_calls,
            "mode": "troubleshoot"
        }
        
    except Exception as e:
        logger.error(f"Troubleshoot chat failed: {e}", exc_info=True)
        return {
            "response": f"I apologize, but I encountered an error: {str(e)}",
            "message": f"I apologize, but I encountered an error: {str(e)}",
            "session_id": session_id,
            "mode": "troubleshoot"
        }


@router.post("/chat/stream")
async def troubleshoot_chat_stream(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Streaming endpoint for troubleshooting chat using Server-Sent Events (SSE).
    Uses TroubleshootingOrchestrator for context enrichment and MCP tools.
    """
    from app.services.agentic.troubleshooting_orchestrator import TroubleshootingOrchestrator
    from app.services.mcp.client import MCPClient
    from app.services.ai_permission_service import AIPermissionService
    
    message = request.get("message", "")
    session_id = request.get("session_id", "")
    
    logger.info(f"Troubleshoot stream from {current_user.username}: {message[:100]}...")
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        nonlocal session_id
        full_response = ""
        tool_calls = []
        
        try:
            # Get Provider
            provider = db.query(LLMProvider).filter(LLMProvider.is_default == True, LLMProvider.is_enabled == True).first()
            if not provider:
                provider = db.query(LLMProvider).filter(LLMProvider.is_enabled == True).first()
            if not provider:
                yield f"data: {json.dumps({'type': 'error', 'content': 'No LLM provider configured'})}\n\n"
                return
            
            # Get Session
            ai_session = None
            initial_messages = []
            
            if session_id:
                try:
                    session_uuid = uuid.UUID(session_id)
                    ai_session = db.query(AISession).filter(AISession.id == session_uuid).first()
                except (ValueError, TypeError):
                    pass
            
            if not ai_session:
                ai_session = AISession(user_id=current_user.id, pillar="troubleshooting", title=message[:100] if message else "Troubleshooting Session")
                db.add(ai_session)
                db.commit()
                db.refresh(ai_session)
                session_id = str(ai_session.id)
            else:
                existing_messages = db.query(AIMessage).filter(AIMessage.session_id == ai_session.id).order_by(AIMessage.created_at).all()
                for msg in existing_messages:
                    initial_messages.append({"role": msg.role, "content": msg.content})
            
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
            
            # Save User Message
            user_msg = AIMessage(session_id=ai_session.id, role="user", content=message)
            db.add(user_msg)
            db.commit()
            
            # Setup Dependencies
            # Context alert_id (attempt to find from session context or request? For now assume None or derive)
            # Logic to find alert_id if not passed explicitly is tricky. 
            # Ideally frontend passes it.
            # Retrieve alert_id from session if not provided
            alert_id = None
            if request.get("alert_id"):
                 try:
                     alert_id = uuid.UUID(request.get("alert_id"))
                 except: pass
            elif ai_session:
                # Try to get from session context
                if ai_session.context_type == 'alert' and ai_session.context_id:
                    alert_id = ai_session.context_id
                elif ai_session.context_context_json and ai_session.context_context_json.get("alert_id"):
                    try:
                        alert_id = uuid.UUID(ai_session.context_context_json.get("alert_id"))
                    except: pass


            # Initialize MCP client with server URL (defaulting to localhost if not configured)
            mcp_server_url = os.getenv("MCP_GRAFANA_URL", "http://localhost:8081")
            mcp_client = MCPClient(server_url=mcp_server_url)
            # Connect MCP client (assuming auto-connect or we trigger it)
            # mcp_client.connect() # implementation detail depends on client
            
            perm_service = AIPermissionService(db)

            orchestrator = TroubleshootingOrchestrator(
                db=db,
                user=current_user,
                alert_id=alert_id,
                mcp_client=mcp_client,
                permission_service=perm_service,
                llm_provider=provider
            )

            # Stream Response
            async for chunk in orchestrator.run_troubleshooting_turn(message, initial_messages):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                await asyncio.sleep(0.01)
            
            # Get tools from orchestrator if available
            if hasattr(orchestrator, 'tool_calls_made'):
                tool_calls = orchestrator.tool_calls_made
            
            # Save Assistant Response
            assistant_msg = AIMessage(
                session_id=ai_session.id,
                role="assistant",
                content=full_response,
                metadata_json={"tool_calls": tool_calls} if tool_calls else None
            )
            db.add(assistant_msg)
            db.commit()
            
            yield f"data: {json.dumps({'type': 'done', 'tool_calls': tool_calls})}\n\n"
            
        except asyncio.CancelledError:
            logger.info("Stream cancelled by client")
            yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/sessions")
async def list_troubleshoot_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List troubleshooting sessions for the current user.
    """
    sessions = db.query(AISession).filter(
        AISession.user_id == current_user.id
    ).order_by(AISession.created_at.desc()).all()
    
    return {
        "sessions": [
            {
                "id": str(s.id),
                "title": s.title or "Untitled Session",
                "created_at": s.created_at.isoformat(),
                "updated_at": s.created_at.isoformat()
            }
            for s in sessions
        ],
        "count": len(sessions)
    }


@router.post("/sessions")
async def create_troubleshoot_session(
    current_user: User = Depends(get_current_user)
):
    """
    Create a new troubleshooting session.
    """
    from uuid import uuid4
    from datetime import datetime
    
    session_id = str(uuid4())
    return {
        "id": session_id,
        "user_id": str(current_user.id),
        "created_at": datetime.utcnow().isoformat(),
        "mode": "troubleshoot"
    }
@router.get("/providers")
async def list_troubleshoot_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List available LLM providers for troubleshooting."""
    from app.llm_core.provider_selection import get_available_providers
    providers = get_available_providers(db)
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "provider_name": f"{p.name} ({p.provider_type})",
            "provider_type": p.provider_type,
            "model_id": p.model_id,
            "is_default": p.is_default,
            "is_enabled": p.is_enabled
        }
        for p in providers
    ]

@router.get("/sessions/standalone")
async def get_standalone_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current standalone troubleshooting session or create one."""
    session = db.query(AISession).filter(
        AISession.user_id == current_user.id,
        AISession.pillar == "troubleshooting",
        AISession.context_type == "standalone"
    ).order_by(AISession.created_at.desc()).first()

    if not session:
        session = AISession(
            user_id=current_user.id,
            pillar="troubleshooting",
            context_type="standalone",
            title="Troubleshooting Session"
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # Get provider ID from context if set
    llm_provider_id = None
    if session.context_context_json:
        llm_provider_id = session.context_context_json.get("llm_provider_id")

    return {
        "id": str(session.id),
        "title": session.title,
        "llm_provider_id": llm_provider_id
    }

@router.get("/sessions/{session_id}/messages")
async def get_troubleshoot_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get messages for a troubleshooting session."""
    try:
        session_uuid = uuid.UUID(session_id)
        messages = db.query(AIMessage).filter(
            AIMessage.session_id == session_uuid
        ).order_by(AIMessage.created_at).all()
        
        return [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "metadata": m.metadata_json
            }
            for m in messages
        ]
    except Exception as e:
        logger.error(f"Failed to get messages: {e}")
        raise HTTPException(status_code=400, detail="Invalid session ID")

@router.patch("/sessions/{session_id}/provider")
async def switch_troubleshoot_provider(
    session_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Switch LLM provider for a session."""
    try:
        provider_id = payload.get("provider_id")
        if not provider_id:
            raise HTTPException(status_code=400, detail="provider_id required")

        session_uuid = uuid.UUID(session_id)
        session = db.query(AISession).filter(
            AISession.id == session_uuid,
            AISession.user_id == current_user.id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        ctx = dict(session.context_context_json) if session.context_context_json else {}
        ctx["llm_provider_id"] = provider_id
        session.context_context_json = ctx
        db.commit()

        return {"success": True}
    except Exception as e:
        logger.error(f"Switch provider failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/commands/validate")
async def validate_command_troubleshoot(
    request: CommandValidateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Validate a command before execution.
    Returns safety assessment and risk level.
    """
    from app.services.command_validator import CommandValidator
    
    try:
        validator = CommandValidator()
        
        # Detect OS type from server name
        os_type = "windows" if any(x in request.server.lower() for x in ['win', 'windows']) else "linux"
        
        # Validate command
        result = validator.validate_command(request.command, os_type)
        
        return {
            "result": result.result.value,
            "message": result.message,
            "risk_level": result.risk_level if hasattr(result, 'risk_level') else 'unknown'
        }
    except Exception as e:
        return {
            "result": "unknown",
            "message": f"Validation error: {str(e)}",
            "risk_level": "unknown"
        }
