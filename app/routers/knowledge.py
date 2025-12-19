"""
Knowledge Base API Router
Handles document and image management
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
import uuid
import logging

from app.database import get_db
from app.models import User
from app.services.auth_service import get_current_user, require_permission
from app.schemas_knowledge import (
    DocumentCreate, DocumentUpdate, DocumentResponse,
    DocumentListResponse, DocumentWithChunks, ChunkResponse,
    KnowledgeSearchQuery, SearchResponse, SearchResult
)
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_search_service import KnowledgeSearchService
from app.services.pdf_service import PDFService
from app.services.vision_ai_service import VisionAIService
import os
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


# ============================================================================
# Document Endpoints
# ============================================================================

@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    title: str = Form(...),
    doc_type: str = Form(...),
    content: str = Form(default=''),
    format: str = Form(default='markdown'),
    file: Optional[UploadFile] = File(None),
    app_id: Optional[str] = Form(None),
    source_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(["upload_documents"]))
):
    """
    Create a new design document.
    
    Supports text, markdown, PDF, and image uploads.
    """
    logger.info(f"=== UPLOAD REQUEST ===")
    logger.info(f"Title: '{title}' (type: {type(title)})")
    logger.info(f"Doc Type: '{doc_type}' (type: {type(doc_type)})")
    logger.info(f"Content length: {len(content)}")
    logger.info(f"Format: '{format}'")
    logger.info(f"File: {file.filename if file else None}")
    logger.info(f"App ID: {app_id}")
    logger.info(f"Source URL: {source_url}")
    logger.info(f"=====================")
    doc_service = DocumentService(db)
    embedding_service = EmbeddingService()
    pdf_service = PDFService()
    vision_service = VisionAIService()
    
    # Handle file upload if provided
    if file:
        file_extension = Path(file.filename).suffix.lower()
        
        # PDF: extract text and images
        if file_extension == '.pdf':
            content = pdf_service.extract_text(file.file) or ""
            if not content.strip():
                raise HTTPException(400, "Failed to extract text from PDF")
            
            # Save PDF temporarily
            storage_dir = Path("./storage/knowledge/documents")
            storage_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = storage_dir / f"{uuid.uuid4()}{file_extension}"
            file.file.seek(0)
            with open(pdf_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            # Extract images from PDF
            extracted_images = pdf_service.extract_images_from_pdf(str(pdf_path))
            
            # Analyze extracted images with Vision AI
            if extracted_images and vision_service.is_configured():
                content += "\n\n---\n# Extracted Diagrams from PDF\n\n"
                
                for img_info in extracted_images:
                    try:
                        analysis = vision_service.analyze_diagram(img_info["path"], doc_type)
                        if analysis:
                            image_analysis = vision_service.generate_searchable_text(analysis)
                            content += f"\n## Diagram from Page {img_info['page']}\n"
                            content += f"*Image size: {img_info['width']}x{img_info['height']}*\n\n"
                            content += image_analysis + "\n\n"
                            logger.info(f"Analyzed image from PDF page {img_info['page']}")
                    except Exception as e:
                        logger.error(f"Failed to analyze PDF image: {e}")
            
            format = 'pdf'
        
        # Images: Vision AI analysis
        elif file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
            storage_dir = Path("./storage/knowledge/images")
            storage_dir.mkdir(parents=True, exist_ok=True)
            image_path = storage_dir / f"{uuid.uuid4()}{file_extension}"
            with open(image_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            if vision_service.is_configured():
                analysis = vision_service.analyze_diagram(str(image_path), doc_type)
                content = vision_service.generate_searchable_text(analysis) if analysis else f"Image: {file.filename}"
            else:
                content = f"Image: {file.filename} (Vision AI not configured)"
            format = 'image'
        
        # Text files
        elif file_extension in ['.txt', '.md', '.markdown']:
            file_content = await file.read()
            content = file_content.decode('utf-8')
    
    # Parse app_id if provided
    app_uuid = None
    if app_id:
        try:
            app_uuid = UUID(app_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid app_id format")
    
    # Create document
    try:
        document = doc_service.create_document(
            title=title,
            doc_type=doc_type,
            content=content,
            format=format,
            app_id=app_uuid,
            user_id=current_user.id,
            source_url=source_url,
            source_type='manual'
        )
        
        # Create chunks
        chunks = doc_service.create_chunks_for_document(document)
        
        # Generate embeddings for chunks (if OpenAI key is configured)
        if embedding_service.is_configured() and chunks:
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = embedding_service.generate_embeddings_batch(chunk_texts)
            
            # Assign embeddings to chunks
            for chunk, embedding in zip(chunks, embeddings):
                if embedding:
                    chunk.embedding = embedding
        
        db.commit()
        db.refresh(document)
        
        logger.info(f"Created document {document.id} with {len(chunks)} chunks")
        
        return document
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    app_id: Optional[UUID] = None,
    doc_type: Optional[str] = None,
    status: str = 'active',
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List documents with optional filters."""
    doc_service = DocumentService(db)
    
    documents, total = doc_service.list_documents(
        app_id=app_id,
        doc_type=doc_type,
        status=status,
        skip=skip,
        limit=limit
    )
    
    return {
        "items": documents,
        "total": total,
        "page": (skip // limit) + 1 if limit > 0 else 1,
        "page_size": limit
    }


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific document by ID."""
    doc_service = DocumentService(db)
    
    document = doc_service.get_document_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return document


@router.get("/documents/{document_id}/chunks", response_model=List[ChunkResponse])
async def get_document_chunks(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all chunks for a document."""
    from app.models_knowledge import DesignChunk
    
    chunks = db.query(DesignChunk).filter(
        DesignChunk.source_type == 'document',
        DesignChunk.source_id == document_id
    ).order_by(DesignChunk.chunk_index).all()
    
    return chunks


@router.put("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    updates: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(["manage_knowledge"]))
):
    """Update a document's metadata."""
    doc_service = DocumentService(db)
    
    document = doc_service.update_document(
        document_id,
        **updates.model_dump(exclude_unset=True)
    )
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    db.commit()
    db.refresh(document)
    
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a document and its chunks."""
    doc_service = DocumentService(db)
    
    if not doc_service.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    
    db.commit()
    
    return None


# ============================================================================
# Search Endpoints
# ============================================================================

@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    query: KnowledgeSearchQuery,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(["view_knowledge"]))
):
    """
    Semantic search across knowledge base.
    
    Uses vector similarity search if embeddings are available,
    otherwise falls back to text-based search.
    """
    import time
    start_time = time.time()
    
    search_service = KnowledgeSearchService(db)
    
    results = search_service.search_similar(
        query=query.query,
        app_id=query.app_id,
        doc_types=query.doc_types,
        content_types=query.content_types,
        limit=query.limit,
        min_similarity=query.min_similarity
    )
    
    logger.info(f"Search for '{query.query}' returned {len(results)} results (min_similarity={query.min_similarity})")
    
    # Fallback to text search if vector search returns nothing and min_similarity > 0
    if len(results) == 0 and query.min_similarity > 0:
        logger.info(f"Falling back to text search for '{query.query}'")
        results = search_service._text_search(
            query=query.query,
            app_id=query.app_id,
            doc_types=query.doc_types,
            limit=query.limit
        )
        logger.info(f"Text search returned {len(results)} results")
    
    processing_time = (time.time() - start_time) * 1000  # Convert to ms
    
    return {
        "query": query.query,
        "results": results,
        "total_found": len(results),
        "processing_time_ms": round(processing_time, 2)
    }


# ============================================================================
# Stats & Summary Endpoints
# ============================================================================

@router.get("/stats")
async def get_knowledge_stats(
    app_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get knowledge base statistics."""
    from app.models_knowledge import DesignDocument, DesignImage, DesignChunk
    from sqlalchemy import func
    
    # Build base query
    doc_query = db.query(DesignDocument)
    chunk_query = db.query(DesignChunk)
    
    if app_id:
        doc_query = doc_query.filter(DesignDocument.app_id == app_id)
        chunk_query = chunk_query.filter(DesignChunk.app_id == app_id)
    
    # Get counts
    total_documents = doc_query.count()
    total_chunks = chunk_query.count()
    
    # Count by doc type
    docs_by_type = db.query(
        DesignDocument.doc_type,
        func.count(DesignDocument.id)
    ).group_by(DesignDocument.doc_type).all()
    
    return {
        "total_documents": total_documents,
        "total_chunks": total_chunks,
        "documents_by_type": {doc_type: count for doc_type, count in docs_by_type},
        "embedding_model": EmbeddingService().get_embedding_model(),
        "embedding_configured": EmbeddingService().is_configured()
    }


# ============================================================================
# Git Sync Endpoints
# ============================================================================

from app.services.git_sync_service import GitSyncService
from pydantic import BaseModel

class GitSyncRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    app_id: Optional[UUID] = None

@router.post("/sync/git", status_code=status.HTTP_200_OK)
async def sync_git_repository(
    sync_req: GitSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(["manage_knowledge"]))
):
    """
    Trigger synchronization from a Git repository.
    Clones the repo and auto-imports all markdown files.
    """
    sync_service = GitSyncService(db)
    try:
        stats = sync_service.sync_repository(
            repo_url=sync_req.repo_url,
            app_id=sync_req.app_id,
            branch=sync_req.branch,
            user_id=current_user.id
        )
        return {
            "message": "Git sync completed",
            "stats": stats,
            "repo_url": sync_req.repo_url
        }
    except Exception as e:
        logger.error(f"Git sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Git sync failed: {str(e)}")
