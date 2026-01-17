"""
File Operations and Change Set Models

Provides SQLAlchemy models for tracking file versions, backups, and atomic change sets.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Text, ForeignKey,
    DateTime, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
# Import dependencies for relationships
from app.models import ServerCredential
from app.models_revive import AISession
from app.models_agent import AgentStep

def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)

class FileVersion(Base):
    """
    Tracks versions of files modified by the agent or user.
    """
    __tablename__ = "file_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ai_sessions.id"), nullable=True)
    server_id = Column(UUID(as_uuid=True), ForeignKey("server_credentials.id"), nullable=True)
    file_path = Column(String(1024), nullable=False)
    content = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True)
    version_number = Column(Integer, default=1)
    created_by = Column(String(50), default='agent')  # 'user', 'agent', 'backup'
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # Relationships
    session = relationship("AISession")
    server = relationship("ServerCredential")
    backups = relationship("FileBackup", back_populates="file_version")


class FileBackup(Base):
    """
    Tracks remote backups of files before modification.
    """
    __tablename__ = "file_backups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_version_id = Column(UUID(as_uuid=True), ForeignKey("file_versions.id"), nullable=False)
    backup_path = Column(String(1024), nullable=False)  # remote backup location
    created_at = Column(DateTime(timezone=True), default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    file_version = relationship("FileVersion", back_populates="backups")


class ChangeSet(Base):
    """
    Represents a group of atomic file changes to be applied together.
    """
    __tablename__ = "change_sets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ai_sessions.id"), nullable=False)
    agent_step_id = Column(UUID(as_uuid=True), ForeignKey("agent_steps.id"), nullable=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default='pending')  # 'pending', 'previewing', 'applied', 'rolled_back'
    created_at = Column(DateTime(timezone=True), default=utc_now)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    rolled_back_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    session = relationship("AISession")
    agent_step = relationship("AgentStep", foreign_keys=[agent_step_id])
    items = relationship("ChangeItem", back_populates="change_set", cascade="all, delete-orphan", order_by="ChangeItem.order_index")


class ChangeItem(Base):
    """
    Individual file operation within a change set.
    """
    __tablename__ = "change_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    change_set_id = Column(UUID(as_uuid=True), ForeignKey("change_sets.id"), nullable=False)
    file_path = Column(String(1024), nullable=False)
    operation = Column(String(50), default='modify')  # 'create', 'modify', 'delete', 'rename'
    old_content = Column(Text, nullable=True)
    new_content = Column(Text, nullable=True)
    diff_hunks = Column(JSON, nullable=True)
    status = Column(String(50), default='pending')  # 'pending', 'accepted', 'rejected', 'applied'
    order_index = Column(Integer, default=0)

    # Relationships
    change_set = relationship("ChangeSet", back_populates="items")
