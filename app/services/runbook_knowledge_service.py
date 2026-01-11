"""
Runbook Knowledge Service
Indexes runbooks into knowledge base for AI-powered search and recommendations
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy. orm import Session

from app.models_remediation import Runbook, RunbookStep
from app.models_knowledge import DesignChunk
from app.services.embedding_service import EmbeddingService
from app.services. document_service import DocumentService

logger = logging.getLogger(__name__)


class RunbookKnowledgeService: 
    """
    Indexes runbooks into the knowledge base for semantic search. 
    Enables AI to find and recommend relevant runbooks for issues.
    """
    
    # NOTE: design_chunks.source_type is constrained to values like 'document'/'image'.
    # Runbooks are indexed as source_type='document' with chunk_metadata.doc_type='runbook'.
    CHUNK_SOURCE_TYPE = "document"
    
    def __init__(self, db: Session):
        self.db = db
        
        # Try to get OpenAI key from DB
        from app.models import LLMProvider
        from app.services.llm_service import get_api_key_for_provider
        
        api_key = None
        try:
            # Find any enabled OpenAI provider
            provider = db.query(LLMProvider).filter(
                LLMProvider.provider_type == 'openai',
                LLMProvider.is_enabled == True
            ).first()
            
            if provider:
                api_key = get_api_key_for_provider(provider)
        except Exception as e:
            logger.error(f"Failed to fetch OpenAI key from DB: {e}")
            
        self.embedding_service = EmbeddingService(api_key=api_key)
        self.doc_service = DocumentService(db)
    
    def index_runbook(self, runbook: Runbook) -> int:
        """
        Index a runbook into the knowledge base. 
        Creates searchable chunks with vector embeddings. 
        
        Returns:
            Number of chunks created
        """
        # Remove existing chunks for this runbook
        self.remove_runbook_from_index(runbook.id)
        
        chunks_created = 0
        
        # Create main runbook description chunk
        main_content = self._build_runbook_content(runbook)
        main_chunk = self._create_chunk(
            runbook=runbook,
            content=main_content,
            content_type="troubleshooting",
            chunk_index=0,
            metadata={
                "runbook_id": str(runbook.id),
                "runbook_name": runbook.name,
                "category": runbook.category,
                "tags": runbook.tags or [],
                "enabled": runbook.enabled,
                "auto_execute": runbook.auto_execute,
                "is_main_chunk": True,
                "doc_type": "runbook",
                "view_url": f"/runbooks/{runbook.id}/view"
            }
        )
        if main_chunk: 
            chunks_created += 1
        
        # Create chunks for each step
        for step in runbook.steps:
            step_content = self._build_step_content(runbook, step)
            step_chunk = self._create_chunk(
                runbook=runbook,
                content=step_content,
                content_type="troubleshooting",
                chunk_index=step.step_order,
                metadata={
                    "runbook_id": str(runbook.id),
                    "runbook_name": runbook.name,
                    "step_id": str(step.id),
                    "step_order": step.step_order,
                    "step_name":  step.name,
                    "target_os": step.target_os,
                    "doc_type": "runbook",
                    "view_url": f"/runbooks/{runbook.id}/view"
                }
            )
            if step_chunk:
                chunks_created += 1
        
        # Index triggers for matching
        for trigger in runbook.triggers:
            if trigger.enabled:
                trigger_content = self._build_trigger_content(runbook, trigger)
                trigger_chunk = self._create_chunk(
                    runbook=runbook,
                    content=trigger_content,
                    content_type="troubleshooting",
                    chunk_index=100 + trigger.priority,
                    metadata={
                        "runbook_id": str(runbook.id),
                        "runbook_name": runbook.name,
                        "trigger_id": str(trigger.id),
                        "doc_type": "runbook",
                        "view_url": f"/runbooks/{runbook.id}/view",
                        "alert_patterns": {
                            "name_pattern": trigger.alert_name_pattern,
                            "severity_pattern": trigger.severity_pattern,
                            "instance_pattern": trigger.instance_pattern
                        }
                    }
                )
                if trigger_chunk: 
                    chunks_created += 1
        
        self.db.commit()
        logger.info(f"Indexed runbook '{runbook.name}' with {chunks_created} chunks")
        return chunks_created
    
    def remove_runbook_from_index(self, runbook_id: UUID) -> int:
        """Remove runbook from knowledge base index."""
        # Only delete chunks that were created for runbooks.
        result = (
            self.db.query(DesignChunk)
            .filter(
                DesignChunk.source_type == self.CHUNK_SOURCE_TYPE,
                DesignChunk.source_id == runbook_id,
                DesignChunk.chunk_metadata["doc_type"].astext == "runbook",
            )
            .delete()
        )
        self.db.commit()
        return result
    
    def reindex_all_runbooks(self) -> Dict[str, int]:
        """Reindex all enabled runbooks."""
        runbooks = self. db.query(Runbook).filter(Runbook.enabled == True).all()
        stats = {"total":  0, "indexed":  0, "chunks":  0}
        
        for runbook in runbooks:
            try:
                chunks = self.index_runbook(runbook)
                stats["indexed"] += 1
                stats["chunks"] += chunks
            except Exception as e: 
                logger.error(f"Failed to index runbook {runbook.id}: {e}")
            stats["total"] += 1
        
        return stats
    
    def search_relevant_runbooks(
        self,
        query: str,
        alert_context: Optional[Dict] = None,
        limit: int = 5,
        min_similarity: float = 0.5
    ) -> List[Dict[str, Any]]: 
        """
        Search for relevant runbooks based on query and optional alert context.
        
        Args:
            query: Natural language query or problem description
            alert_context: Optional alert information for better matching
            limit: Maximum results
            min_similarity:  Minimum similarity threshold
            
        Returns: 
            List of matching runbooks with relevance scores
        """
        # Build enhanced query with alert context
        enhanced_query = self._enhance_query(query, alert_context)
        
        # Generate embedding for query
        query_embedding = self. embedding_service.generate_embedding(enhanced_query)
        if not query_embedding: 
            logger.warning("Failed to generate query embedding")
            return []
        
        # Search using vector similarity
        from sqlalchemy import text
        
        sql = text("""
            SELECT 
                c.source_id as runbook_id,
                c.chunk_metadata->>'runbook_name' as runbook_name,
                c.content,
                c. content_type,
                c.chunk_metadata as metadata,
                1 - (c.embedding <=> CAST(: query_embedding AS vector)) as similarity
            FROM design_chunks c
            WHERE c.source_type = 'document'
                AND c.chunk_metadata->>'doc_type' = 'runbook'
                AND c.embedding IS NOT NULL
                AND 1 - (c.embedding <=> CAST(:query_embedding AS vector)) >= :min_similarity
            ORDER BY c.embedding <=> CAST(: query_embedding AS vector)
            LIMIT :limit
        """)
        
        try:
            result = self.db.execute(sql, {
                "query_embedding": query_embedding,
                "min_similarity": min_similarity,
                "limit": limit * 2  # Get more for deduplication
            })
            rows = result.fetchall()
            
            # Deduplicate by runbook_id, keeping highest score
            seen = {}
            for row in rows:
                runbook_id = str(row. runbook_id)
                if runbook_id not in seen or row.similarity > seen[runbook_id]["similarity"]:
                    # Load full runbook
                    runbook = self.db.query(Runbook).filter(Runbook.id == row.runbook_id).first()
                    if runbook and runbook.enabled:
                        seen[runbook_id] = {
                            "runbook_id": runbook_id,
                            "runbook_name": runbook.name,
                            "description": runbook.description,
                            "category": runbook.category,
                            "tags": runbook. tags or [],
                            "similarity": float(row.similarity),
                            "matched_content_type": row.content_type,
                            "auto_execute": runbook.auto_execute,
                            "approval_required": runbook.approval_required,
                            "view_url": f"/runbooks/{runbook_id}/view",
                            "steps_count": len(runbook.steps)
                        }
            
            # Sort by similarity and limit
            results = sorted(seen.values(), key=lambda x:  x["similarity"], reverse=True)[:limit]
            return results
            
        except Exception as e:
            logger.error(f"Runbook search failed: {e}")
            return []
    
    def _build_runbook_content(self, runbook: Runbook) -> str:
        """Build searchable content from runbook."""
        parts = [
            f"Runbook: {runbook.name}",
            f"Description: {runbook. description or 'No description'}",
            f"Category: {runbook.category or 'Uncategorized'}",
        ]
        
        if runbook.tags:
            parts.append(f"Tags:  {', '.join(runbook.tags)}")
        
        # Add step summaries
        if runbook.steps:
            parts.append("\nSteps:")
            for step in sorted(runbook.steps, key=lambda s: s.step_order):
                parts.append(f"  {step.step_order}. {step.name}:  {step.description or ''}")
        
        # Add trigger patterns for matching
        if runbook.triggers:
            parts.append("\nTrigger patterns:")
            for trigger in runbook.triggers:
                if trigger.enabled:
                    parts.append(f"  - Alert: {trigger.alert_name_pattern}, Severity: {trigger.severity_pattern}")
        
        return "\n".join(parts)
    
    def _build_step_content(self, runbook:  Runbook, step:  RunbookStep) -> str:
        """Build searchable content from step."""
        parts = [
            f"Runbook Step: {step.name}",
            f"Part of runbook: {runbook.name}",
            f"Description: {step.description or 'No description'}",
        ]
        
        if step.command_linux:
            parts. append(f"Linux command: {step.command_linux[: 200]}")
        if step.command_windows:
            parts. append(f"Windows command: {step. command_windows[:200]}")
        
        return "\n".join(parts)
    
    def _build_trigger_content(self, runbook, trigger) -> str:
        """Build searchable content from trigger."""
        parts = [
            f"Runbook trigger for:  {runbook.name}",
            f"Triggers on alert: {trigger.alert_name_pattern}",
            f"Severity: {trigger.severity_pattern}",
            f"Instance: {trigger. instance_pattern}",
        ]
        return "\n".join(parts)
    
    def _enhance_query(self, query: str, alert_context: Optional[Dict]) -> str:
        """Enhance search query with alert context."""
        if not alert_context: 
            return query
        
        enhanced_parts = [query]
        
        if alert_context.get("alert_name"):
            enhanced_parts.append(f"Alert: {alert_context['alert_name']}")
        if alert_context. get("severity"):
            enhanced_parts.append(f"Severity: {alert_context['severity']}")
        if alert_context.get("instance"):
            enhanced_parts.append(f"Instance:  {alert_context['instance']}")
        if alert_context.get("description"):
            enhanced_parts.append(alert_context["description"])
        
        return " ".join(enhanced_parts)
    
    def _create_chunk(
        self,
        runbook: Runbook,
        content: str,
        content_type: str,
        chunk_index: int,
        metadata: Dict
    ) -> Optional[DesignChunk]:
        """Create a knowledge chunk with embedding."""
        try:
            # Generate embedding
            embedding = None
            if self.embedding_service. is_configured():
                embedding = self.embedding_service.generate_embedding(content)
            
            chunk = DesignChunk(
                source_type=self. CHUNK_SOURCE_TYPE,
                source_id=runbook.id,
                chunk_index=chunk_index,
                content=content,
                content_type=content_type,
                embedding=embedding,
                chunk_metadata=metadata
            )
            
            self.db. add(chunk)
            return chunk
            
        except Exception as e: 
            logger.error(f"Failed to create chunk: {e}")
            return None

    @staticmethod
    def index_runbook_background_task(runbook_id: UUID):
        """
        Background task to index a runbook.
        Creates its own synchronous DB session.
        """
        from app.database import SessionLocal
        from sqlalchemy.orm import selectinload
        
        # Import ALL models to ensure ORM mapping registry is complete
        import app.models
        import app.models_application
        import app.models_application_knowledge
        import app.models_dashboards
        import app.models_group
        import app.models_itsm
        import app.models_knowledge
        import app.models_learning
        import app.models_remediation
        import app.models_revive
        import app.models_runbook_acl
        import app.models_scheduler
        import app.models_troubleshooting
        import app.models_zombies
        
        logger.info(f"Starting background indexing for runbook {runbook_id}")
        db = SessionLocal()
        try:
            # Load runbook with ALL relationships needed for indexing
            runbook = db.query(Runbook).options(
                selectinload(Runbook.steps),
                selectinload(Runbook.triggers)
            ).filter(Runbook.id == runbook_id).first()
            
            if not runbook:
                logger.warning(f"Runbook {runbook_id} not found during background indexing")
                return
                
            service = RunbookKnowledgeService(db)
            chunks = service.index_runbook(runbook)
            logger.info(f"Background indexing completed for {runbook.id}: {chunks} chunks")
            
        except Exception as e:
            import traceback
            logger.error(f"Background indexing failed for {runbook_id}: {e}\n{traceback.format_exc()}")
        finally:
            db.close()