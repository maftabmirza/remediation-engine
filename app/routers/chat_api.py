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

from app.database import get_db
from app.models import User, LLMProvider
from app.services.auth_service import get_current_user
from app.models_revive import AISession, AIMessage

router = APIRouter(prefix="/api/chat", tags=["chat"])


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
        "is_standalone": True
    }


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

        session_uuid = UUID(session_id)
        session = db.query(AISession).filter(
            AISession.id == session_uuid,
            AISession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # Verify provider exists
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        
        # Save provider selection in context for now (until we add column)
        if not session.context_context_json:
            session.context_context_json = {}
        
        ctx = dict(session.context_context_json) if session.context_context_json else {}
        ctx["llm_provider_id"] = provider_id
        session.context_context_json = ctx
        
        db.commit()
        
        return {
            "success": True, 
            "session_id": session_id,
            "provider_name": provider.name,
            "model_name": provider.model_id
        }
    except ValueError:
         raise HTTPException(status_code=400, detail="Invalid session ID")


# WebSocket endpoint for chat - gracefully close since chat is REST-based
@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for chat status updates.
    In this implementation, chat is primarily REST-based.
    """
    await websocket.close(code=1000, reason="Chat uses REST API")
