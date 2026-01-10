"""
AI Helper Database Models
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class AISession(Base):
    __tablename__ = "ai_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    title = Column(String(255), nullable=True)
    context_context_json = Column(JSON, nullable=True) # Page context when session started
    
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    messages = relationship("AIMessage", back_populates="session", cascade="all, delete-orphan", order_by="AIMessage.created_at")
    user = relationship("User")

class AIMessage(Base):
    __tablename__ = "ai_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=False)
    
    role = Column(String(20), nullable=False) # user, assistant, system
    content = Column(Text, nullable=False)
    
    # Metadata for rich responses (e.g., cited runbooks, executed queries)
    metadata_json = Column(JSON, nullable=True) 
    
    created_at = Column(DateTime(timezone=True), default=utc_now)

    session = relationship("AISession", back_populates="messages")
