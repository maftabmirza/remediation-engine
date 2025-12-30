"""
Chat API endpoints (REST)
"""
from uuid import UUID
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Alert, LLMProvider
from app.models_chat import ChatSession, ChatMessage
from app.services.auth_service import get_current_user
from pydantic import BaseModel

from app.services.similarity_service import SimilarityService
from app.models_learning import AnalysisFeedback

router = APIRouter(prefix="/api/chat", tags=["Chat"])

class ContextStatusResponse(BaseModel):
    has_similar_incidents: bool
    similar_count: int
    has_feedback_history: bool
    has_correlation: bool

class ChatSessionCreate(BaseModel):
    alert_id: Optional[UUID] = None
    llm_provider_id: Optional[UUID] = None
    title: Optional[str] = None

class ChatSessionResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    llm_provider_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class ChatSessionListItem(BaseModel):
    id: UUID
    title: Optional[str] = None
    created_at: datetime
    message_count: int

@router.get("/sessions", response_model=List[ChatSessionListItem])
async def list_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all chat sessions for the current user"""
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()
    
    return [
        ChatSessionListItem(
            id=s.id,
            title=s.title or "Untitled Session",
            created_at=s.created_at,
            message_count=len(s.messages)
        )
        for s in sessions
    ]

@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat session, optionally linked to an alert"""
    title = data.title or "AI Chat"
    
    if data.alert_id:
        alert = db.query(Alert).filter(Alert.id == data.alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        if not data.title:
            title = f"Chat about {alert.alert_name}"
        
    session = ChatSession(
        user_id=current_user.id,
        alert_id=data.alert_id,
        llm_provider_id=data.llm_provider_id,
        title=title
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None

@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: UUID,
    data: UpdateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a chat session (e.g. title)"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if data.title is not None:
        session.title = data.title
        session.updated_at = datetime.utcnow()

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
        "provider_name": provider.name,
        "model_name": provider.model_id
    }


# LLM Providers endpoint for the chat interface
class LLMProviderListResponse(BaseModel):
    id: UUID
    provider_name: str
    model_name: str
    is_default: bool
    is_enabled: bool

    class Config:
        from_attributes = True


@router.get("/providers", response_model=List[LLMProviderListResponse])
async def list_chat_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available LLM providers for chat (enabled only)"""
    providers = db.query(LLMProvider).filter(LLMProvider.is_enabled == True).all()

    return [
        LLMProviderListResponse(
            id=p.id,
            provider_name=p.name,
            model_name=p.model_id,
            is_default=p.is_default,
            is_enabled=p.is_enabled
        )
        for p in providers
    ]


@router.get("/sessions/by-alert/{alert_id}", response_model=ChatSessionResponse)
async def get_session_by_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the most recent chat session for an alert (to reuse existing session)"""
    session = db.query(ChatSession).filter(
        ChatSession.alert_id == alert_id,
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.created_at.desc()).first()

    if not session:
        raise HTTPException(status_code=404, detail="No session found for this alert")

    return session


@router.get("/sessions/standalone", response_model=ChatSessionResponse)
async def get_or_create_standalone_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the most recent standalone chat session or create a new one"""
    # Look for existing standalone session (no alert_id)
    session = db.query(ChatSession).filter(
        ChatSession.alert_id == None,
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.created_at.desc()).first()

    if not session:
        # Create new standalone session
        session = ChatSession(
            user_id=current_user.id,
            alert_id=None,
            title="AI Chat"
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    return session

@router.get("/context-status/{alert_id}", response_model=ContextStatusResponse)
async def get_context_status(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check what context is available for the AI prompts.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    # Check similar incidents
    similar_count = 0
    try:
        sim_service = SimilarityService(db)
        sim_resp = sim_service.find_similar_alerts(alert.id, limit=3)
        if sim_resp:
            similar_count = sim_resp.total_found
    except Exception:
        pass
        
    # Check feedback history (mock check for now, or real if we query by alert text/signature)
    # Ideally we'd checking for feedback on *similar* alerts, or just general feedback existence
    has_feedback = db.query(AnalysisFeedback).count() > 0
    
    # Check correlation
    has_correlation = alert.correlation_id is not None
    
    return ContextStatusResponse(
        has_similar_incidents=similar_count > 0,
        similar_count=similar_count,
        has_feedback_history=has_feedback,
        has_correlation=has_correlation
    )
