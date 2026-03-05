"""
RAG-Enhanced Alert Diagnosis Service (Feature B7)

Uses Retrieval-Augmented Generation (RAG) to enrich alert analysis by
fetching relevant context from two sources:

  1. **Similar historical alerts** — previous alerts whose embedding vector is
     close to the current alert's embedding (via pgvector cosine similarity).
  2. **Knowledge-base chunks** — design documents / SOPs stored in
     ``design_chunks`` whose content is semantically similar to the alert.

The retrieved context is formatted into a prompt section that is prepended to
the standard LLM analysis prompt, allowing the model to reference past
resolutions and documented procedures.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Alert
from app.models_knowledge import DesignChunk, DesignDocument
from app.schemas import (
    RAGDiagnosisContext,
    RAGKnowledgeChunk,
    RAGSimilarIncident,
)
from app.services.embedding_service import EmbeddingService
from app.services.similarity_service import SimilarityService

logger = logging.getLogger(__name__)

# Maximum number of similar incidents / knowledge chunks to include
_MAX_SIMILAR_INCIDENTS = 5
_MAX_KNOWLEDGE_CHUNKS = 5
# Minimum similarity threshold for knowledge-base chunks
_MIN_CHUNK_SIMILARITY = 0.30
# Excerpt length for context text
_EXCERPT_MAX_CHARS = 400


class RagAlertDiagnosisService:
    """
    Retrieves RAG context for alert diagnosis.

    Combines vector-similar historical alerts with relevant knowledge-base
    chunks to produce a rich context block that can be injected into LLM
    prompts.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.embedding_service = EmbeddingService(db=db)
        self.similarity_service = SimilarityService(db)

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def get_context(
        self,
        alert: Alert,
        max_similar_incidents: int = _MAX_SIMILAR_INCIDENTS,
        max_knowledge_chunks: int = _MAX_KNOWLEDGE_CHUNKS,
    ) -> RAGDiagnosisContext:
        """
        Build the RAG context for an alert.

        Args:
            alert:                  The alert being diagnosed.
            max_similar_incidents:  Maximum historical alerts to retrieve.
            max_knowledge_chunks:   Maximum knowledge-base chunks to retrieve.

        Returns:
            RAGDiagnosisContext populated with similar incidents and knowledge
            chunks, plus a pre-formatted ``context_text`` ready for prompt
            injection.
        """
        similar_incidents = self._get_similar_incidents(alert, max_similar_incidents)
        knowledge_chunks = self._get_knowledge_chunks(alert, max_knowledge_chunks)
        context_text = self._format_context_text(similar_incidents, knowledge_chunks)

        return RAGDiagnosisContext(
            similar_incidents=similar_incidents,
            knowledge_chunks=knowledge_chunks,
            context_text=context_text,
        )

    def build_rag_prompt_section(self, context: RAGDiagnosisContext) -> str:
        """
        Return the context_text from a RAGDiagnosisContext.

        This is a convenience wrapper so callers don't need to reach inside the
        context object.

        Args:
            context: Previously retrieved RAG context.

        Returns:
            Formatted string to prepend to the LLM prompt, or empty string when
            the context contains no useful information.
        """
        return context.context_text

    # ──────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────

    def _get_similar_incidents(
        self,
        alert: Alert,
        limit: int,
    ) -> List[RAGSimilarIncident]:
        """
        Retrieve historically similar alerts using pgvector.

        Falls back to an empty list if the alert has no embedding yet (e.g.
        the embedding worker has not yet processed the new alert).

        Args:
            alert: The alert to search neighbours for.
            limit: Maximum number of similar incidents to return.

        Returns:
            List of RAGSimilarIncident objects ordered by similarity (desc).
        """
        if not alert.embedding:
            logger.debug(
                "Alert %s has no embedding — skipping similar-incident retrieval", alert.id
            )
            return []

        try:
            response = self.similarity_service.find_similar_alerts(
                alert_id=alert.id,
                limit=limit,
            )
            if not response:
                return []

            results: List[RAGSimilarIncident] = []
            for incident in response.similar_incidents:
                # Fetch the AI analysis for the similar alert to include an excerpt
                similar_alert = self.db.query(Alert).filter(Alert.id == incident.alert_id).first()
                analysis_excerpt: Optional[str] = None
                if similar_alert and similar_alert.ai_analysis:
                    analysis_excerpt = similar_alert.ai_analysis[:_EXCERPT_MAX_CHARS]

                results.append(
                    RAGSimilarIncident(
                        alert_id=incident.alert_id,
                        alert_name=incident.alert_name,
                        similarity_score=incident.similarity_score,
                        occurred_at=incident.occurred_at,
                        severity=incident.severity,
                        instance=incident.instance,
                        ai_analysis_excerpt=analysis_excerpt,
                    )
                )
            return results
        except Exception:
            logger.exception("Failed to retrieve similar incidents for alert %s", alert.id)
            return []

    def _get_knowledge_chunks(
        self,
        alert: Alert,
        limit: int,
    ) -> List[RAGKnowledgeChunk]:
        """
        Search the knowledge base for chunks relevant to this alert.

        Builds a text query from alert fields, generates an embedding, and
        performs a pgvector similarity search against ``design_chunks``.

        Falls back to an empty list if the embedding service is not configured.

        Args:
            alert: The alert being diagnosed.
            limit: Maximum number of knowledge chunks to return.

        Returns:
            List of RAGKnowledgeChunk objects ordered by similarity (desc).
        """
        if not self.embedding_service.is_configured():
            logger.debug("Embedding service not configured — skipping knowledge-base retrieval")
            return []

        query_text = self._build_query_text(alert)
        query_embedding = self.embedding_service.generate_embedding(query_text)
        if not query_embedding:
            logger.warning("Failed to generate query embedding for alert %s", alert.id)
            return []

        try:
            # Use raw pgvector ordering — cosine distance = 1 - similarity
            from sqlalchemy import text as sql_text

            rows = (
                self.db.query(
                    DesignChunk,
                    (1 - DesignChunk.embedding.cosine_distance(query_embedding)).label("similarity"),
                )
                .filter(
                    DesignChunk.embedding.isnot(None),
                    DesignChunk.embedding.cosine_distance(query_embedding)
                    <= (1 - _MIN_CHUNK_SIMILARITY),
                )
                .order_by(DesignChunk.embedding.cosine_distance(query_embedding))
                .limit(limit)
                .all()
            )
        except Exception:
            logger.exception("Vector search failed for alert %s", alert.id)
            return []

        results: List[RAGKnowledgeChunk] = []
        for chunk, similarity in rows:
            # Resolve the parent document title
            doc_title = "Unknown document"
            doc_type: Optional[str] = None
            if chunk.source_type == "document":
                doc = self.db.query(DesignDocument).filter(
                    DesignDocument.id == chunk.source_id
                ).first()
                if doc:
                    doc_title = doc.title
                    doc_type = doc.doc_type

            results.append(
                RAGKnowledgeChunk(
                    chunk_id=chunk.id,
                    document_title=doc_title,
                    content_excerpt=chunk.content[:_EXCERPT_MAX_CHARS],
                    similarity_score=round(float(similarity), 4),
                    doc_type=doc_type,
                )
            )
        return results

    @staticmethod
    def _build_query_text(alert: Alert) -> str:
        """
        Construct a natural-language query from alert fields for embedding.

        Args:
            alert: The alert to build a query for.

        Returns:
            A descriptive query string.
        """
        parts = [f"Alert: {alert.alert_name}"]
        if alert.severity:
            parts.append(f"Severity: {alert.severity}")
        if alert.instance:
            parts.append(f"Instance: {alert.instance}")
        if alert.job:
            parts.append(f"Job: {alert.job}")
        annotations = alert.annotations_json or {}
        if annotations.get("summary"):
            parts.append(f"Summary: {annotations['summary']}")
        if annotations.get("description"):
            parts.append(f"Description: {annotations['description']}")
        return "\n".join(parts)

    @staticmethod
    def _format_context_text(
        similar_incidents: List[RAGSimilarIncident],
        knowledge_chunks: List[RAGKnowledgeChunk],
    ) -> str:
        """
        Format retrieved context into a human-readable prompt section.

        Args:
            similar_incidents: Previously similar alerts.
            knowledge_chunks:  Relevant knowledge-base chunks.

        Returns:
            A formatted multi-line string, or empty string when both lists are
            empty.
        """
        if not similar_incidents and not knowledge_chunks:
            return ""

        sections: List[str] = ["## Retrieved Context (RAG)"]

        if similar_incidents:
            sections.append("\n### Similar Historical Incidents")
            for i, inc in enumerate(similar_incidents, start=1):
                occurred = (
                    inc.occurred_at.strftime("%Y-%m-%d %H:%M UTC")
                    if isinstance(inc.occurred_at, datetime)
                    else str(inc.occurred_at)
                )
                sections.append(
                    f"{i}. **{inc.alert_name}** "
                    f"(similarity: {inc.similarity_score:.0%}, "
                    f"severity: {inc.severity or 'unknown'}, "
                    f"instance: {inc.instance or 'unknown'}, "
                    f"occurred: {occurred})"
                )
                if inc.ai_analysis_excerpt:
                    sections.append(f"   _Previous analysis_: {inc.ai_analysis_excerpt}")

        if knowledge_chunks:
            sections.append("\n### Relevant Knowledge Base")
            for i, chunk in enumerate(knowledge_chunks, start=1):
                sections.append(
                    f"{i}. **{chunk.document_title}** "
                    f"(similarity: {chunk.similarity_score:.0%}"
                    + (f", type: {chunk.doc_type}" if chunk.doc_type else "")
                    + ")"
                )
                sections.append(f"   {chunk.content_excerpt}")

        return "\n".join(sections)
