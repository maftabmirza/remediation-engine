"""
Document Processing Service
Handles document upload, text chunking, and content processing
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import hashlib

from sqlalchemy.orm import Session
from app.models_knowledge import DesignDocument, DesignChunk
from app.models_application import Application


class DocumentService:
    """Service for processing and chunking documents."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def chunk_text(
        self, 
        text: str, 
        chunk_size: int = 1000, 
        overlap: int = 200,
        preserve_paragraphs: bool = True
    ) -> List[str]:
        """
        Intelligently chunk text into smaller pieces.
        
        Args:
            text: Text to chunk
            chunk_size: Target size of each chunk in characters
            overlap: Number of characters to overlap between chunks
            preserve_paragraphs: Try to keep paragraphs together
            
        Returns:
            List of text chunks
        """
        if not text or len(text) == 0:
            return []
        
        chunks = []
        
        if preserve_paragraphs:
            # Split by double newlines (paragraphs)
            paragraphs = re.split(r'\n\s*\n', text)
            current_chunk = ""
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                
                # If adding this paragraph exceeds chunk size
                if len(current_chunk) + len(para) + 2 > chunk_size and current_chunk:
                    chunks.append(current_chunk.strip())
                    # Add overlap from end of current chunk
                    if overlap > 0 and len(current_chunk) > overlap:
                        current_chunk = current_chunk[-overlap:] + "\n\n" + para
                    else:
                        current_chunk = para
                else:
                    if current_chunk:
                        current_chunk += "\n\n" + para
                    else:
                        current_chunk = para
            
            # Add remaining chunk
            if current_chunk:
                chunks.append(current_chunk.strip())
        else:
            # Simple character-based chunking
            start = 0
            while start < len(text):
                end = start + chunk_size
                chunk = text[start:end]
                chunks.append(chunk.strip())
                start = end - overlap
        
        return chunks
    
    def process_markdown(self, content: str) -> Dict[str, Any]:
        """
        Extract metadata from markdown content.
        
        Args:
            content: Markdown content
            
        Returns:
            Dictionary with extracted metadata
        """
        metadata = {
            'headers': [],
            'code_blocks': 0,
            'links': [],
            'has_toc': False
        }
        
        # Extract headers
        header_pattern = r'^#{1,6}\s+(.+)$'
        headers = re.findall(header_pattern, content, re.MULTILINE)
        metadata['headers'] = headers
        
        # Count code blocks
        code_block_pattern = r'```[\s\S]*?```'
        metadata['code_blocks'] = len(re.findall(code_block_pattern, content))
        
        # Extract links
        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        links = re.findall(link_pattern, content)
        metadata['links'] = [{'text': text, 'url': url} for text, url in links]
        
        # Check for table of contents
        metadata['has_toc'] = bool(re.search(r'#+\s*table\s+of\s+contents', content, re.IGNORECASE))
        
        return metadata
    
    def generate_slug(self, title: str) -> str:
        """
        Generate URL-safe slug from title.
        
        Args:
            title: Document title
            
        Returns:
            URL-safe slug
        """
        # Convert to lowercase and replace spaces with hyphens
        slug = title.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug[:500]  # Limit length
    
    def create_document(
        self,
        title: str,
        doc_type: str,
        content: str,
        format: str = 'markdown',
        app_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        source_url: Optional[str] = None,
        source_type: str = 'manual'
    ) -> DesignDocument:
        """
        Create a new design document.
        
        Args:
            title: Document title
            doc_type: Type of document (architecture, sop, etc.)
            content: Raw document content
            format: Document format (markdown, pdf, html, yaml)
            app_id: Related application ID
            user_id: Creating user ID
            source_url: Source URL if synced
            source_type: Source type (git, confluence, manual)
            
        Returns:
            Created DesignDocument instance
        """
        # Generate unique slug
        base_slug = self.generate_slug(title)
        slug = base_slug
        counter = 1
        
        while self.db.query(DesignDocument).filter(DesignDocument.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        # Create document
        document = DesignDocument(
            title=title,
            slug=slug,
            doc_type=doc_type,
            format=format,
            raw_content=content,
            app_id=app_id,
            source_url=source_url,
            source_type=source_type,
            created_by=user_id,
            status='active',
            version=1
        )
        
        self.db.add(document)
        self.db.flush()  # Get the ID without committing
        
        return document
    
    def create_chunks_for_document(
        self,
        document: DesignDocument,
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> List[DesignChunk]:
        """
        Create text chunks for a document.
        
        Args:
            document: DesignDocument instance
            chunk_size: Target chunk size
            overlap: Overlap between chunks
            
        Returns:
            List of created DesignChunk instances
        """
        if not document.raw_content:
            return []
        
        # Delete existing chunks for this document to avoid duplication on re-sync
        self.db.query(DesignChunk).filter(
            DesignChunk.source_id == document.id,
            DesignChunk.source_type == 'document'
        ).delete(synchronize_session=False)
        
        # Chunk the text
        text_chunks = self.chunk_text(
            document.raw_content,
            chunk_size=chunk_size,
            overlap=overlap
        )
        
        # Create DesignChunk instances
        chunks = []
        for idx, content in enumerate(text_chunks):
            chunk = DesignChunk(
                app_id=document.app_id,
                source_type='document',
                source_id=document.id,
                chunk_index=idx,
                content=content,
                content_type='text',
                chunk_metadata={
                    'doc_title': document.title,
                    'doc_type': document.doc_type,
                    'chunk_size': len(content),
                    'format': document.format
                }
            )
            self.db.add(chunk)
            chunks.append(chunk)
        
        return chunks
    
    def get_document_by_id(self, document_id: UUID) -> Optional[DesignDocument]:
        """Get document by ID."""
        return self.db.query(DesignDocument).filter(
            DesignDocument.id == document_id
        ).first()
    
    def get_document_by_slug(self, slug: str) -> Optional[DesignDocument]:
        """Get document by slug."""
        return self.db.query(DesignDocument).filter(
            DesignDocument.slug == slug
        ).first()
    
    def list_documents(
        self,
        app_id: Optional[UUID] = None,
        doc_type: Optional[str] = None,
        status: str = 'active',
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[DesignDocument], int]:
        """
        List documents with filters.
        
        Returns:
            Tuple of (documents list, total count)
        """
        query = self.db.query(DesignDocument)
        
        if app_id:
            query = query.filter(DesignDocument.app_id == app_id)
        if doc_type:
            query = query.filter(DesignDocument.doc_type == doc_type)
        if status:
            query = query.filter(DesignDocument.status == status)
        
        total = query.count()
        documents = query.order_by(DesignDocument.created_at.desc()).offset(skip).limit(limit).all()
        
        return documents, total
    
    def update_document(
        self,
        document_id: UUID,
        **updates
    ) -> Optional[DesignDocument]:
        """Update document fields."""
        document = self.get_document_by_id(document_id)
        if not document:
            return None
        
        for key, value in updates.items():
            if hasattr(document, key) and value is not None:
                setattr(document, key, value)
        
        return document
    
    def delete_document(self, document_id: UUID) -> bool:
        """Delete document and associated chunks."""
        document = self.get_document_by_id(document_id)
        if not document:
            return False
        
        self.db.delete(document)
        return True
