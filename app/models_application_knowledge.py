"""
Application Knowledge Configuration Models
"""
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.database import Base

class ApplicationKnowledgeConfig(Base):
    __tablename__ = "application_knowledge_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Git Configuration
    git_repo_url = Column(String, nullable=True)
    git_branch = Column(String, default="main")
    git_auth_type = Column(String, default="none")  # none, token, ssh, basic
    git_token = Column(String, nullable=True)  # Store encrypted if possible
    
    # Sync Settings
    sync_docs = Column(Boolean, default=True)
    sync_code = Column(Boolean, default=False)
    doc_patterns = Column(JSON, default=lambda: ["*.md", "docs/**/*"])
    exclude_patterns = Column(JSON, default=lambda: ["**/node_modules/**", "**/.git/**"])
    
    # Automation
    auto_sync_enabled = Column(Boolean, default=False)
    sync_interval_hours = Column(Integer, default=24)
    
    # Status
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_status = Column(String, nullable=True)  # success, failed, in_progress
    last_sync_stats = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    application = relationship("Application", back_populates="knowledge_config")
