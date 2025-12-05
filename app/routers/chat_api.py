"""
Chat API endpoints (REST)
"""
from uuid import UUID
from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Alert, LLMProvider
from app.models_chat import ChatSession, ChatMessage
from app.services.auth_service import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/api/chat", tags=["Chat"])

class ChatSessionCreate(BaseModel):
    alert_id: UUID
    llm_provider_id: UUID = None

class ChatSessionResponse(BaseModel):
    id: UUID
    title: str = None
    llm_provider_id: UUID = None
    created_at: datetime

    class Config:
        from_attributes = True

class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat session for an alert"""
    alert = db.query(Alert).filter(Alert.id == data.alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    session = ChatSession(
        user_id=current_user.id,
        alert_id=data.alert_id,
        llm_provider_id=data.llm_provider_id,
        title=f"Chat about {alert.alert_name}"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_messages(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get message history for a session"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()

    return messages

class UpdateProviderRequest(BaseModel):
    provider_id: UUID

@router.patch("/sessions/{session_id}/provider")
async def update_session_provider(
    session_id: UUID,
    data: UpdateProviderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the LLM provider for a chat session"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    provider = db.query(LLMProvider).filter(
        LLMProvider.id == data.provider_id,
        LLMProvider.is_enabled == True
    ).first()

    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found or disabled")

    session.llm_provider_id = data.provider_id
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)

    return {
        "status": "success",
        "provider_name": provider.provider_name,
        "model_name": provider.model_name
    }
