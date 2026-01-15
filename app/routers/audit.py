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
from app.models_revive import AISession, AIMessage

from app.services.auth_service import require_admin
from app.config import get_settings

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


class TerminalRecordingResponse(BaseModel):
    session_id: UUID
    content: str


class ChatSessionListItem(BaseModel):
    id: UUID
    created_at: datetime
    username: str
    title: Optional[str] = None
    message_count: int = 0


class PaginatedChatSessionsResponse(BaseModel):
    items: List[ChatSessionListItem]
    total: int
    page: int
    limit: int


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime


@router.get("/logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    limit: int = Query(200, ge=1, le=1000),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return recent audit logs (admin only)."""
    logs = (
        db.query(AuditLog)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .all()
    )

    out: List[AuditLogResponse] = []
    for log in logs:
        out.append(
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                username=log.user.username if getattr(log, "user", None) else None,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details_json=log.details_json,
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
        )
    return out


@router.get("/terminal-sessions", response_model=List[TerminalSessionResponse])
def list_terminal_sessions(
    limit: int = Query(200, ge=1, le=1000),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return recent terminal sessions (admin only)."""
    sessions = (
        db.query(TerminalSession)
        .order_by(desc(TerminalSession.started_at))
        .limit(limit)
        .all()
    )

    out: List[TerminalSessionResponse] = []
    for s in sessions:
        server_name = None
        try:
            server_name = s.server.name if s.server else None
        except Exception:
            server_name = None
        out.append(
            TerminalSessionResponse(
                id=s.id,
                user_id=s.user_id,
                username=s.user.username if s.user else "Unknown",
                server_name=server_name or "Unknown",
                started_at=s.started_at,
                ended_at=s.ended_at,
                has_recording=bool(s.recording_path),
            )
        )
    return out


@router.get("/terminal-sessions/{session_id}/recording", response_model=TerminalRecordingResponse)
def get_terminal_recording(
    session_id: UUID,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return terminal recording content (admin only)."""
    session = db.query(TerminalSession).filter(TerminalSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Terminal session not found")

    if not session.recording_path:
        raise HTTPException(status_code=404, detail="No recording available")

    settings = get_settings()
    recording_dir = os.path.abspath(settings.recording_dir)
    path = os.path.abspath(session.recording_path)

    # Prevent reading arbitrary files
    if not path.startswith(recording_dir + os.sep) and path != recording_dir:
        raise HTTPException(status_code=403, detail="Recording path not allowed")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Recording file not found")

    # Cap content size for UI safety
    max_bytes = 200_000
    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        content = data[:max_bytes].decode("utf-8", errors="replace")
        if truncated:
            content += "\n\n[...truncated...]"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read recording: {e}")

    return TerminalRecordingResponse(session_id=session.id, content=content)


@router.get("/chat-sessions", response_model=PaginatedChatSessionsResponse)
def list_chat_sessions(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List AI chat sessions (admin only) with pagination."""
    total = db.query(func.count(AISession.id)).scalar() or 0
    offset = (page - 1) * limit

    sessions = (
        db.query(AISession)
        .order_by(desc(AISession.updated_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    session_ids = [s.id for s in sessions]
    counts = {}
    if session_ids:
        rows = (
            db.query(AIMessage.session_id, func.count(AIMessage.id))
            .filter(AIMessage.session_id.in_(session_ids))
            .group_by(AIMessage.session_id)
            .all()
        )
        counts = {sid: int(cnt) for sid, cnt in rows}

    items: List[ChatSessionListItem] = []
    for s in sessions:
        username = "System"
        try:
            if s.user and getattr(s.user, "username", None):
                username = s.user.username
        except Exception:
            pass

        items.append(
            ChatSessionListItem(
                id=s.id,
                created_at=s.created_at,
                username=username,
                title=s.title,
                message_count=counts.get(s.id, 0),
            )
        )

    return PaginatedChatSessionsResponse(items=items, total=int(total), page=page, limit=limit)


@router.get("/chat-sessions/{session_id}/transcript", response_model=List[ChatMessageResponse])
def get_chat_transcript(
    session_id: UUID,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return transcript messages for a chat session (admin only)."""
    session = db.query(AISession).filter(AISession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = (
        db.query(AIMessage)
        .filter(AIMessage.session_id == session_id)
        .order_by(AIMessage.created_at)
        .all()
    )

    return [
        ChatMessageResponse(role=m.role, content=m.content, created_at=m.created_at)
        for m in messages
    ]


