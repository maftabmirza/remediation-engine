"""
Chat API Router

Provides API endpoints for the AI chat interface.
Wraps around existing settings/providers functionality.
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
import json
from pydantic import BaseModel

from app.database import get_db
from app.models import User, LLMProvider
from app.services.auth_service import get_current_user
from app.models_revive import AISession, AIMessage

router = APIRouter(prefix="/api/chat", tags=["chat"])


# Request models
class CommandValidateRequest(BaseModel):
    command: str
    server: str


@router.get("/providers")
async def get_chat_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get available LLM providers for chat.
    Returns enabled providers in a format suitable for the chat UI.
    """
    providers = db.query(LLMProvider).filter(LLMProvider.is_enabled == True).all()
    
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
    current_user: User = Depends(get_current_user)
):
    """
    Get or create a standalone chat session.
    For the AI chat page, we use a simple session model.
    """
    # Return a session object with the user's default session
    return {
        "id": f"session-{current_user.id}",
        "user_id": str(current_user.id),
        "created_at": datetime.utcnow().isoformat(),
        "is_standalone": True,
        "llm_provider_id": str(current_user.default_llm_provider_id) if current_user.default_llm_provider_id else None,
    }


@router.get("/sessions/by-alert/{alert_id}")
async def get_session_by_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the chat session associated with an alert for the current user.
    """
    try:
        alert_uuid = UUID(alert_id)
        # Find existing session for this alert and user
        # Note: We don't have a direct alert_id on AISession, but we might store it in context
        # Ideally, we should check for a session that has this alert in context
        
        # Searching by context_json logic
        # For now, let's look for a session that has "alert_id": alert_id in its context
        # This is a bit inefficient without a dedicated column/index, but OK for now
        
        sessions = db.query(AISession).filter(
            AISession.user_id == current_user.id
        ).order_by(AISession.updated_at.desc()).limit(20).all()
        
        for session in sessions:
            if session.context_context_json and session.context_context_json.get("alert_id") == alert_id:
                return {
                    "id": str(session.id),
                    "user_id": str(session.user_id),
                    "title": session.title,
                    "created_at": session.created_at.isoformat()
                }
        
        # If not found, return 404 - let frontend create one
        raise HTTPException(status_code=404, detail="Session not found for this alert")
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert ID")


@router.get("/context-status/{alert_id}")
async def get_context_status(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check status of analysis context for an alert.
    """
    # This endpoint is polled by frontend to see if context (e.g. analysis) is ready
    # For now, we can just return a basic "ready" status if the alert exists
    from app.models import Alert
    
    try:
        alert_uuid = UUID(alert_id)
        alert = db.query(Alert).filter(Alert.id == alert_uuid).first()
        
        if not alert:
             raise HTTPException(status_code=404, detail="Alert not found")
             
        return {
            "status": "ready",
            "analyzed": alert.analyzed,
            "analysis_available": bool(alert.ai_analysis)
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert ID")


@router.get("/sessions")
async def list_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List chat sessions for the current user.
    """
    sessions = db.query(AISession).filter(
        AISession.user_id == current_user.id
    ).order_by(AISession.updated_at.desc()).all()
    
    return {
        "sessions": [
            {
                "id": str(s.id),
                "title": s.title or "Untitled Session",
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "message_count": len(s.messages)
            }
            for s in sessions
        ],
        "count": len(sessions)
    }


@router.post("/sessions")
async def create_chat_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new chat session.
    """
    session_id = uuid4()
    new_session = AISession(
        id=session_id,
        user_id=current_user.id,
        title="New Chat",
        created_at=datetime.utcnow()
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return {
        "id": str(session_id),
        "user_id": str(current_user.id),
        "created_at": new_session.created_at.isoformat()
    }


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get messages for a chat session.
    """
    try:
        session_uuid = UUID(session_id)
        # Verify ownership
        session = db.query(AISession).filter(
            AISession.id == session_uuid,
            AISession.user_id == current_user.id
        ).first()
        
        if not session:
            # Check if it is a standalone session (special handling)
            if session_id.startswith("session-"):
                 return []
            raise HTTPException(status_code=404, detail="Session not found")
        
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
    except ValueError:
        return []


@router.patch("/sessions/{session_id}/provider")
async def switch_session_provider(
    session_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Switch the LLM provider for a chat session.
    """
    try:
        provider_id = payload.get("provider_id")
        if not provider_id:
             raise HTTPException(status_code=400, detail="provider_id is required")

        # Provider IDs are UUIDs in the DB; normalize early for consistent queries.
        try:
            provider_uuid = UUID(str(provider_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid provider ID")

        # Verify provider exists
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_uuid).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        # Standalone chat uses IDs like "session-<user_id>" (not stored in ai_sessions).
        # For this mode, persist the selection as the user's default LLM provider.
        if session_id.startswith("session-"):
            current_user.default_llm_provider_id = provider_uuid
            db.commit()
            return {
                "success": True,
                "session_id": session_id,
                "provider_name": provider.name,
                "model_name": provider.model_id,
            }

        # Normal persisted AI sessions
        session_uuid = UUID(session_id)
        session = db.query(AISession).filter(
            AISession.id == session_uuid,
            AISession.user_id == current_user.id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Save provider selection in session context for now (until we add column)
        ctx = dict(session.context_context_json) if session.context_context_json else {}
        ctx["llm_provider_id"] = str(provider_uuid)
        session.context_context_json = ctx

        db.commit()

        return {
            "success": True,
            "session_id": session_id,
            "provider_name": provider.name,
            "model_name": provider.model_id,
        }
    except ValueError:
         raise HTTPException(status_code=400, detail="Invalid session ID")


@router.post("/commands/validate")
async def validate_command(
    request: CommandValidateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Validate a command before execution.
    Returns safety assessment and risk level.
    """
    from app.services.command_validator import CommandValidator, ValidationResult
    
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


# WebSocket endpoint for chat - gracefully close since chat is REST-based
# WebSocket endpoint for chat
@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for chat status updates.
    Keeps connection alive for real-time notifications.
    """
    await websocket.accept()
    try:
        while True:
            # Simple keep-alive loop
            # In a full implementation, we would subscribe to a message queue here
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
