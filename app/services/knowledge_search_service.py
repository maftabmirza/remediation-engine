"""
Knowledge Search Service
Semantic search across design documents using vector similarity
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models_knowledge import DesignChunk, DesignDocument, DesignImage
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class KnowledgeSearchService:
    """Service for searching knowledge base using vector similarity."""
    
    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService()
    
    def search_similar(
        self,
        query: str,
        app_id: Optional[UUID] = None,
        doc_types: Optional[List[str]] = None,
        content_types: Optional[List[str]] = None,
        limit: int = 10,
        min_similarity: float = 0.3  # Lowered from 0.7 for better recall
    ) -> List[Dict[str, Any]]:
        """
        Search for similar knowledge chunks using semantic search.
        
        Args:
            query: Search query text
            app_id: Filter by application ID
            doc_types: Filter by document types
            content_types: Filter by content types
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold (0-1)
            
        Returns:
            List of search results with similarity scores
        """
        if not self.embedding_service.is_configured():
            logger.warning("Embedding service not configured - falling back to text search")
            return self._text_search(query, app_id, doc_types, limit)
        
        # Generate embedding for query
        query_embedding = self.embedding_service.generate_embedding(query)
        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return self._text_search(query, app_id, doc_types, limit)
        
        return self.search_by_embedding(
            query_embedding,
            app_id=app_id,
            doc_types=doc_types,
            content_types=content_types,
            limit=limit,
            min_similarity=min_similarity
        )
    
    def search_by_embedding(
        self,
        embedding: List[float],
        app_id: Optional[UUID] = None,
        doc_types: Optional[List[str]] = None,
        content_types: Optional[List[str]] = None,
        limit: int = 10,
        min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search using a pre-computed embedding vector.
        
        Args:
            embedding: The query embedding vector
            app_id: Filter by application ID
            doc_types: Filter by document types
            content_types: Filter by content types
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of search results with similarity scores
        """
        # Build SQL query with vector similarity
        # Using cosine distance: 1 - (embedding <=> query_embedding)
        
        filters = []
        params = {
            'query_embedding': embedding,
            'limit': limit,
            'min_similarity': min_similarity
        }
        
        if app_id:
            filters.append("c.app_id = :app_id")
            params['app_id'] = str(app_id)
        
        if content_types:
            filters.append("c.content_type = ANY(:content_types)")
            params['content_types'] = content_types
        
        where_clause = " AND ".join(filters) if filters else "1=1"
        
        sql = text(f"""
            SELECT 
                c.id,
                c.source_type,
                c.source_id,
                c.content,
                c.content_type,
                c.chunk_metadata,
                1 - (c.embedding <=> CAST(:query_embedding AS vector)) as similarity
            FROM design_chunks c
            WHERE {where_clause}
                AND c.embedding IS NOT NULL
                AND 1 - (c.embedding <=> CAST(:query_embedding AS vector)) >= :min_similarity
            ORDER BY c.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :limit
        """)
        
        try:
            result = self.db.execute(sql, params)
            chunks = result.fetchall()
            
            # Enrich results with source information
            enriched_results = []
            for chunk in chunks:
                result_dict = {
                    'chunk_id': chunk.id,
                    'source_type': chunk.source_type,
                    'source_id': chunk.source_id,
                    'content': chunk.content,
                    'content_type': chunk.content_type,
                    'similarity': float(chunk.similarity),
                    'metadata': chunk.chunk_metadata or {}
                }
                
                # Get source object details
                if chunk.source_type == 'document':
                    doc = self.db.query(DesignDocument).filter(
                        DesignDocument.id == chunk.source_id
                    ).first()
                    if doc:
                        result_dict['source_title'] = doc.title
                        result_dict['source_url'] = doc.source_url
                        result_dict['doc_type'] = doc.doc_type
                        result_dict['app_id'] = doc.app_id
                
                elif chunk.source_type == 'image':
                    img = self.db.query(DesignImage).filter(
                        DesignImage.id == chunk.source_id
                    ).first()
                    if img:
                        result_dict['source_title'] = img.title
                        result_dict['image_type'] = img.image_type
                        result_dict['app_id'] = img.app_id
                
                enriched_results.append(result_dict)
            
            return enriched_results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def _text_search(
        self,
        query: str,
        app_id: Optional[UUID] = None,
        doc_types: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Fallback text-based search when embeddings are not available.
        Uses PostgreSQL full-text search.
        
        Args:
            query: Search query
            app_id: Filter by application
            doc_types: Filter by document types
            limit: Maximum results
            
        Returns:
            List of search results
        """
        # Build query
        chunks_query = self.db.query(DesignChunk)
        
        if app_id:
            chunks_query = chunks_query.filter(DesignChunk.app_id == app_id)
        
        # Simple text search using ILIKE
        chunks_query = chunks_query.filter(
            DesignChunk.content.ilike(f'%{query}%')
        )
        
        chunks = chunks_query.limit(limit).all()
        
        # Format and enrich results
        results = []
        for chunk in chunks:
            result = {
                'chunk_id': chunk.id,
                'source_type': chunk.source_type,
                'source_id': chunk.source_id,
                'content': chunk.content,
                'content_type': chunk.content_type,
                'similarity': 0.5,  # Placeholder score for text search
                'metadata': chunk.chunk_metadata or {}
            }
            
            # Enrich with source information
            if chunk.source_type == 'document':
                doc = self.db.query(DesignDocument).filter(
                    DesignDocument.id == chunk.source_id
                ).first()
                if doc:
                    result['source_title'] = doc.title
                    result['source_url'] = doc.source_url
                    result['doc_type'] = doc.doc_type
                    result['app_id'] = doc.app_id
            
            elif chunk.source_type == 'image':
                img = self.db.query(DesignImage).filter(
                    DesignImage.id == chunk.source_id
                ).first()
                if img:
                    result['source_title'] = img.title
                    result['image_type'] = img.image_type
                    result['app_id'] = img.app_id
            
            results.append(result)
        
        return results
