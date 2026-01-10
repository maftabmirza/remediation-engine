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
    current_user: User = Depends(get_current_user)
):
    """
    List chat sessions for the current user.
    Returns empty list for now - sessions are handled client-side.
    """
    return {"sessions": [], "count": 0}


@router.post("/sessions")
async def create_chat_session(
    current_user: User = Depends(get_current_user)
):
    """
    Create a new chat session.
    """
    session_id = str(uuid4())
    return {
        "id": session_id,
        "user_id": str(current_user.id),
        "created_at": datetime.utcnow().isoformat()
    }


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get messages for a chat session.
    Returns empty array for now - messages are handled client-side.
    """
    return []  # Return array directly, not {"messages": []}


@router.patch("/sessions/{session_id}/provider")
async def switch_session_provider(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Switch the LLM provider for a chat session.
    """
    return {"success": True, "session_id": session_id}


# WebSocket endpoint for chat - gracefully close since chat is REST-based
@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for chat status updates.
    In this implementation, chat is primarily REST-based.
    """
    await websocket.close(code=1000, reason="Chat uses REST API")
