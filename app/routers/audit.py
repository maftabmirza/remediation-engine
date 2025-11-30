"""
Audit API endpoints
"""
import os
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from pydantic import BaseModel

from app.database import get_db
from app.models import User, AuditLog, TerminalSession, ServerCredential
from app.models_chat import ChatSession, ChatMessage
from app.services.auth_service import require_admin

router = APIRouter(prefix="/api/audit", tags=["Audit"])

class AuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    username: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    details_json: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class TerminalSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: str
    server_name: str
    started_at: datetime
    ended_at: Optional[datetime]
    has_recording: bool

    class Config:
        from_attributes = True

class ChatSessionAuditResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: str
    title: Optional[str]
    created_at: datetime
    message_count: int

    class Config:
        from_attributes = True

class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class PaginatedChatSessions(BaseModel):
    items: List[ChatSessionAuditResponse]
    total: int
    page: int
    size: int

@router.get("/logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List system audit logs. Admin only.
    """
    logs = db.query(AuditLog).order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()
    
    # Enrich with username manually to avoid N+1 if not eager loaded, 
    # though SQLAlchemy usually handles this. 
    # We'll map it to the response model.
    result = []
    for log in logs:
        resp = AuditLogResponse.model_validate(log)
        if log.user:
            resp.username = log.user.username
        result.append(resp)
        
    return result

@router.get("/terminal-sessions", response_model=List[TerminalSessionResponse])
async def list_terminal_sessions(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List terminal sessions. Admin only.
    """
    sessions = db.query(TerminalSession).order_by(desc(TerminalSession.started_at)).offset(offset).limit(limit).all()
    
    result = []
    for session in sessions:
        result.append(TerminalSessionResponse(
            id=session.id,
            user_id=session.user_id,
            username=session.user.username if session.user else "Unknown",
            server_name=session.server.name if session.server else "Unknown",
            started_at=session.started_at,
            ended_at=session.ended_at,
            has_recording=bool(session.recording_path and os.path.exists(session.recording_path))
        ))
        
    return result

@router.get("/terminal-sessions/{session_id}/recording")
async def get_session_recording(
    session_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get the recording content for a terminal session.
    """
    session = db.query(TerminalSession).filter(TerminalSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if not session.recording_path or not os.path.exists(session.recording_path):
        raise HTTPException(status_code=404, detail="Recording file not found")
        
    try:
        with open(session.recording_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading recording: {str(e)}")

@router.get("/chat-sessions", response_model=PaginatedChatSessions)
async def list_chat_sessions(
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List chat sessions with pagination. Admin only.
    Filters out sessions with 0 messages.
    """
    offset = (page - 1) * limit

    # Count total unique sessions that have messages
    # We use a separate query for count to avoid complexity with group_by count
    total = db.query(ChatSession).join(ChatMessage).distinct().count()

    # Query sessions that have messages
    # Inner join with ChatMessage ensures we only get sessions with messages
    query = db.query(ChatSession, func.count(ChatMessage.id).label('msg_count'))\
        .join(ChatMessage, ChatSession.id == ChatMessage.session_id)\
        .group_by(ChatSession.id)\
        .order_by(desc(ChatSession.created_at))
    
    results = query.offset(offset).limit(limit).all()
    
    items = []
    for session, count in results:
        items.append(ChatSessionAuditResponse(
            id=session.id,
            user_id=session.user_id,
            username=session.user.username if session.user else "Unknown",
            title=session.title or "Untitled Chat",
            created_at=session.created_at,
            message_count=count
        ))
        
    return PaginatedChatSessions(
        items=items,
        total=total,
        page=page,
        size=limit
    )

@router.get("/chat-sessions/{session_id}/transcript", response_model=List[ChatMessageResponse])
async def get_chat_transcript(
    session_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get the transcript for a chat session.
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    return messages
