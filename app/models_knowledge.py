"""
SQLAlchemy models for Knowledge Base
Handles design documents, images, and chunked content with vector embeddings
"""
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime, timezone

from app.database import Base
from app.models_application import Application


def utc_now():
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class DesignDocument(Base):
    """Design documents (SOPs, architecture docs, runbooks, etc.)"""
    __tablename__ = "design_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Document metadata
    title = Column(String(500), nullable=False)
    slug = Column(String(500), unique=True, index=True)
    doc_type = Column(String(50), nullable=False, index=True)
    format = Column(String(20), nullable=False)
    
    # Content
    raw_content = Column(Text, nullable=True)
    
    # Source tracking
    source_url = Column(String(1000), nullable=True)
    source_type = Column(String(50), nullable=True)  # 'git', 'confluence', 'manual'
    
    # Versioning
    version = Column(Integer, default=1)
    status = Column(String(20), default='active', index=True)
    
    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    # Relationships
    application = relationship("Application", back_populates="design_documents")
    creator = relationship("User", foreign_keys=[created_by])
    images = relationship("DesignImage", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DesignChunk", 
                         primaryjoin="and_(DesignDocument.id==foreign(DesignChunk.source_id), DesignChunk.source_type=='document')",
                         cascade="all, delete-orphan",
                         viewonly=True)
    
    __table_args__ = (
        CheckConstraint(
            doc_type.in_(['architecture', 'api_spec', 'runbook', 'sop', 'troubleshooting', 'design_doc', 'postmortem', 'onboarding']),
            name='ck_design_documents_doc_type'
        ),
        CheckConstraint(
            format.in_(['markdown', 'pdf', 'html', 'yaml']),
            name='ck_design_documents_format'
        ),
    )


class DesignImage(Base):
    """Design images (architecture diagrams, flowcharts, etc.)"""
    __tablename__ = "design_images"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("design_documents.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Image metadata
    title = Column(String(500), nullable=False)
    image_type = Column(String(50), nullable=False, index=True)
    
    # Storage
    storage_path = Column(String(1000), nullable=False)
    thumbnail_path = Column(String(1000), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    # AI-extracted information
    ai_description = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    identified_components = Column(JSONB, nullable=True)
    identified_connections = Column(JSONB, nullable=True)
    failure_scenarios = Column(JSONB, nullable=True)
    
    # Processing status
    processing_status = Column(String(20), default='pending', index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    
    # Relationships
    application = relationship("Application", back_populates="design_images")
    document = relationship("DesignDocument", back_populates="images")
    creator = relationship("User", foreign_keys=[created_by])
    chunks = relationship("DesignChunk",
                         primaryjoin="and_(DesignImage.id==foreign(DesignChunk.source_id), DesignChunk.source_type=='image')",
                         cascade="all, delete-orphan",
                         viewonly=True)
    
    __table_args__ = (
        CheckConstraint(
            image_type.in_(['architecture', 'flowchart', 'sequence', 'erd', 'network', 'deployment', 'component', 'other']),
            name='ck_design_images_image_type'
        ),
    )


class DesignChunk(Base):
    """Chunked content with vector embeddings for semantic search"""
    __tablename__ = "design_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Source tracking (polymorphic)
    source_type = Column(String(50), nullable=False)  # 'document', 'image', 'component', 'alert_history'
    source_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_index = Column(Integer, default=0)
    
    # Content
    content = Column(Text, nullable=False)
    content_type = Column(String(50), nullable=False)
    
    # Vector embedding (1536 dimensions for OpenAI text-embedding-3-small)
    embedding = Column(Vector(1536), nullable=True)
    
    # Metadata for filtering (renamed from 'metadata' which is reserved)
    chunk_metadata = Column(JSONB, default={})
    
    created_at = Column(DateTime(timezone=True), default=utc_now)
    
    # Relationships
    application = relationship("Application", back_populates="design_chunks")
    
    __table_args__ = (
        CheckConstraint(
            source_type.in_(['document', 'image', 'component', 'alert_history']),
            name='ck_design_chunks_source_type'
        ),
        CheckConstraint(
            content_type.in_(['text', 'image_description', 'ocr', 'component_info', 'failure_mode', 'troubleshooting', 'dependency_info']),
            name='ck_design_chunks_content_type'
        ),
        Index('design_chunks_source_idx', 'source_type', 'source_id'),
        Index('design_chunks_metadata_idx', 'chunk_metadata', postgresql_using='gin'),
    )
