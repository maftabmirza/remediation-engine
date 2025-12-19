"""
Pydantic schemas for Knowledge Base
Request and response models for design documents, images, and chunks
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime


# ============================================================================
# Design Document Schemas
# ============================================================================

class DocumentBase(BaseModel):
    """Base schema for design documents."""
    title: str = Field(..., max_length=500, description="Document title")
    doc_type: str = Field(..., description="Type of document")
    app_id: Optional[UUID] = Field(None, description="Related application ID")
    description: Optional[str] = Field(None, description="Document description")
    source_url: Optional[str] = Field(None, max_length=1000, description="Source URL")
    source_type: Optional[str] = Field(None, description="Source type (git, confluence, manual)")
    
    @validator('doc_type')
    def validate_doc_type(cls, v):
        valid_types = ['architecture', 'api_spec', 'runbook', 'sop', 'troubleshooting', 'design_doc', 'postmortem', 'onboarding', 'deployment', 'config']
        if v not in valid_types:
            raise ValueError(f"doc_type must be one of: {', '.join(valid_types)}")
        return v


class DocumentCreate(DocumentBase):
    """Schema for creating a design document."""
    format: str = Field(..., description="Document format (markdown, pdf, html, yaml)")
    raw_content: Optional[str] = Field(None, description="Raw document content")
    
    @validator('format')
    def validate_format(cls, v):
        valid_formats = ['markdown', 'pdf', 'html', 'yaml', 'text', 'image']
        if v not in valid_formats:
            raise ValueError(f"format must be one of: {', '.join(valid_formats)}")
        return v


class DocumentUpdate(BaseModel):
    """Schema for updating a design document."""
    title: Optional[str] = Field(None, max_length=500)
    doc_type: Optional[str] = None
    description: Optional[str] = None
    raw_content: Optional[str] = None
    source_url: Optional[str] = None
    status: Optional[str] = None
    
    @validator('doc_type')
    def validate_doc_type(cls, v):
        if v is not None:
            valid_types = ['architecture', 'api_spec', 'runbook', 'sop', 'troubleshooting', 'design_doc', 'postmortem', 'onboarding', 'deployment', 'config']
            if v not in valid_types:
                raise ValueError(f"doc_type must be one of: {', '.join(valid_types)}")
        return v
    
    @validator('status')
    def validate_status(cls, v):
        if v is not None and v not in ['active', 'archived', 'draft']:
            raise ValueError("status must be one of: active, archived, draft")
        return v


class DocumentResponse(DocumentBase):
    """Schema for design document response."""
    id: UUID
    slug: Optional[str]
    raw_content: Optional[str] = Field(None, description="Full document content")
    format: str
    version: int
    status: str
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    chunk_count: Optional[int] = Field(None, description="Number of chunks generated")
    
    class Config:
        from_attributes = True


class DocumentWithChunks(DocumentResponse):
    """Document response with chunks."""
    chunks: List['ChunkResponse'] = []


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""
    items: List[DocumentResponse]
    total: int
    page: int = 1
    page_size: int = 50


# ============================================================================
# Design Image Schemas
# ============================================================================

class ImageBase(BaseModel):
    """Base schema for design images."""
    title: str = Field(..., max_length=500, description="Image title")
    image_type: str = Field(..., description="Type of image/diagram")
    app_id: Optional[UUID] = Field(None, description="Related application ID")
    document_id: Optional[UUID] = Field(None, description="Related document ID")
    
    @validator('image_type')
    def validate_image_type(cls, v):
        valid_types = ['architecture', 'flowchart', 'sequence', 'erd', 'network', 'deployment', 'component', 'other']
        if v not in valid_types:
            raise ValueError(f"image_type must be one of: {', '.join(valid_types)}")
        return v


class ImageCreate(ImageBase):
    """Schema for creating a design image (metadata only, file uploaded separately)."""
    pass


class ImageUpdate(BaseModel):
    """Schema for updating image metadata."""
    title: Optional[str] = Field(None, max_length=500)
    image_type: Optional[str] = None
    document_id: Optional[UUID] = None


class ImageAnalysisResponse(BaseModel):
    """Vision AI analysis results."""
    ai_description: Optional[str] = Field(None, description="AI-generated description")
    extracted_text: Optional[str] = Field(None, description="OCR extracted text")
    identified_components: Optional[List[Dict[str, Any]]] = Field(None, description="Components found in image")
    identified_connections: Optional[List[Dict[str, Any]]] = Field(None, description="Connections/flows found")
    failure_scenarios: Optional[List[Dict[str, Any]]] = Field(None, description="Inferred failure scenarios")


class ImageResponse(ImageBase):
    """Schema for image response."""
    id: UUID
    storage_path: str
    thumbnail_path: Optional[str]
    file_size_bytes: Optional[int]
    mime_type: Optional[str]
    processing_status: str
    processed_at: Optional[datetime]
    created_by: Optional[UUID]
    created_at: datetime
    
    # AI analysis results
    analysis: Optional[ImageAnalysisResponse] = None
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_orm_with_analysis(cls, obj):
        """Create response with analysis data."""
        data = {
            'id': obj.id,
            'title': obj.title,
            'image_type': obj.image_type,
            'app_id': obj.app_id,
            'document_id': obj.document_id,
            'storage_path': obj.storage_path,
            'thumbnail_path': obj.thumbnail_path,
            'file_size_bytes': obj.file_size_bytes,
            'mime_type': obj.mime_type,
            'processing_status': obj.processing_status,
            'processed_at': obj.processed_at,
            'created_by': obj.created_by,
            'created_at': obj.created_at,
            'analysis': ImageAnalysisResponse(
                ai_description=obj.ai_description,
                extracted_text=obj.extracted_text,
                identified_components=obj.identified_components,
                identified_connections=obj.identified_connections,
                failure_scenarios=obj.failure_scenarios
            ) if obj.ai_description or obj.extracted_text else None
        }
        return cls(**data)


class ImageListResponse(BaseModel):
    """Paginated list of images."""
    items: List[ImageResponse]
    total: int
    page: int = 1
    page_size: int = 50


# ============================================================================
# Design Chunk Schemas
# ============================================================================

class ChunkBase(BaseModel):
    """Base schema for design chunks."""
    app_id: Optional[UUID] = None
    source_type: str = Field(..., description="Type of source (document, image, etc.)")
    source_id: UUID = Field(..., description="ID of source object")
    chunk_index: int = Field(0, description="Position in source")
    content: str = Field(..., description="Chunk content")
    content_type: str = Field(..., description="Type of content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('source_type')
    def validate_source_type(cls, v):
        valid_types = ['document', 'image', 'component', 'alert_history']
        if v not in valid_types:
            raise ValueError(f"source_type must be one of: {', '.join(valid_types)}")
        return v
    
    @validator('content_type')
    def validate_content_type(cls, v):
        valid_types = ['text', 'image_description', 'ocr', 'component_info', 'failure_mode', 'troubleshooting', 'dependency_info']
        if v not in valid_types:
            raise ValueError(f"content_type must be one of: {', '.join(valid_types)}")
        return v


class ChunkCreate(ChunkBase):
    """Schema for creating a chunk."""
    embedding: Optional[List[float]] = Field(None, description="1536-dimensional embedding vector")


class ChunkResponse(ChunkBase):
    """Schema for chunk response."""
    id: UUID
    created_at: datetime
    similarity_score: Optional[float] = Field(None, description="Similarity score (for search results)")
    
    class Config:
        from_attributes = True


class ChunkListResponse(BaseModel):
    """Paginated list of chunks."""
    items: List[ChunkResponse]
    total: int
    page: int = 1
    page_size: int = 50


# ============================================================================
# Search Schemas
# ============================================================================

class KnowledgeSearchQuery(BaseModel):
    """Schema for knowledge base search."""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    app_id: Optional[UUID] = Field(None, description="Filter by application")
    doc_types: Optional[List[str]] = Field(None, description="Filter by document types")
    content_types: Optional[List[str]] = Field(None, description="Filter by content types")
    limit: int = Field(10, ge=1, le=50, description="Number of results")
    min_similarity: float = Field(0.7, ge=0.0, le=1.0, description="Minimum similarity threshold")


class SearchResult(BaseModel):
    """Single search result."""
    chunk_id: UUID
    source_type: str
    source_id: UUID
    content: str
    content_type: str
    similarity: float
    metadata: Dict[str, Any] = {}
    
    # Source object details (if available)
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    app_id: Optional[UUID] = None


class SearchResponse(BaseModel):
    """Search results response."""
    query: str
    results: List[SearchResult]
    total_found: int
    processing_time_ms: Optional[float] = None


# ============================================================================
# Statistics and Summary Schemas
# ============================================================================

class KnowledgeSummary(BaseModel):
    """Summary of knowledge base for an application."""
    app_id: UUID
    app_name: str
    total_documents: int
    total_images: int
    total_chunks: int
    documents_by_type: Dict[str, int] = {}
    images_by_type: Dict[str, int] = {}
    last_updated: Optional[datetime] = None


# Update forward references
DocumentWithChunks.model_rebuild()
