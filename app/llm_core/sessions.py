"""
Shared LLM Session Management
"""
import logging
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models_revive import AISession, AIMessage

logger = logging.getLogger(__name__)

def create_session(
    db: Session,
    user_id: int,
    pillar: str,
    title: str = "New Session",
    context_type: Optional[str] = None,
    context_id: Optional[str] = None,
    context_json: Optional[Dict[str, Any]] = None
) -> AISession:
    """Create a new AI session."""
    session_id = uuid4()
    
    new_session = AISession(
        id=session_id,
        user_id=user_id,
        pillar=pillar,
        title=title,
        created_at=datetime.utcnow(),
        context_type=context_type,
        context_id=context_id,
        context_context_json=context_json
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

def get_session(db: Session, session_id: str, user_id: int) -> Optional[AISession]:
    """Get an AI session and verify ownership."""
    try:
        session_uuid = UUID(session_id)
        return db.query(AISession).filter(
            AISession.id == session_uuid,
            AISession.user_id == user_id
        ).first()
    except (ValueError, TypeError):
        return None

def add_message(
    db: Session,
    session_id: UUID,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> AIMessage:
    """Add a message to a session."""
    message = AIMessage(
        id=uuid4(),
        session_id=session_id,
        role=role,
        content=content,
        created_at=datetime.utcnow(),
        metadata_json=metadata
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
