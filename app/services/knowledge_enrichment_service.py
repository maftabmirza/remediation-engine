"""
Knowledge Enrichment Service

RAG-enhanced context injection for all 5 AI interaction points.
Fetches relevant design document chunks, architecture diagram descriptions,
and past resolved alerts to provide grounded context to LLM prompts.
"""
import logging
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Alert
from app.models_knowledge import DesignChunk, DesignImage

logger = logging.getLogger(__name__)

# Approximate characters per token (used for truncation budget)
_CHARS_PER_TOKEN = 4
_MAX_TOKENS = 2000
_MAX_CHARS = _MAX_TOKENS * _CHARS_PER_TOKEN


class KnowledgeEnrichmentService:
    """
    Retrieves knowledge-base context relevant to an alert and formats it
    for injection into LLM system/user prompts.

    Sources (ranked by relevance):
    1. DesignChunk records (pgvector cosine similarity or ILIKE text fallback)
    2. DesignImage.ai_description for the matched application
    3. Successfully resolved Alert records with high embedding similarity
    """

    def __init__(self, db: Session) -> None:
        """
        Initialise the service.

        Args:
            db: SQLAlchemy synchronous session.
        """
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_context_for_alert(
        self,
        alert: Alert,
        max_chunks: int = 5,
        min_similarity: float = 0.5,
    ) -> str:
        """
        Build a formatted knowledge-context string for *alert*.

        Args:
            alert: The Alert ORM object to enrich context for.
            max_chunks: Maximum number of design-doc chunks to include.
            min_similarity: Minimum cosine similarity for vector search.

        Returns:
            A markdown-formatted string (≤ 2000 tokens) or empty string
            when no relevant context is found.
        """
        try:
            parts: List[str] = []

            # 1. Design-document chunks
            chunks = self._fetch_chunks(alert, max_chunks, min_similarity)
            if chunks:
                parts.append("## Relevant Knowledge Base Sections\n")
                for chunk in chunks:
                    parts.append(f"- {chunk['content']}\n")

            # 2. Architecture-diagram descriptions
            img_context = self._fetch_image_descriptions(alert)
            if img_context:
                parts.append("\n## Architecture Context\n")
                parts.append(img_context)

            # 3. Past resolved similar alerts
            resolved_context = self._fetch_resolved_alerts(alert)
            if resolved_context:
                parts.append("\n## Past Resolved Incidents\n")
                parts.append(resolved_context)

            if not parts:
                return ""

            full_context = "".join(parts)
            return self._truncate(full_context)

        except Exception as exc:
            logger.warning(
                "KnowledgeEnrichmentService failed for alert %s: %s",
                alert.id if alert else "unknown",
                exc,
            )
            return ""

    def get_context_for_alert_id(
        self,
        alert_id: UUID,
        max_chunks: int = 5,
        min_similarity: float = 0.5,
    ) -> str:
        """
        Convenience wrapper that looks up the alert by *alert_id* first.

        Args:
            alert_id: Primary key of the Alert record.
            max_chunks: Maximum number of design-doc chunks to include.
            min_similarity: Minimum cosine similarity for vector search.

        Returns:
            Formatted context string or empty string on failure.
        """
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if alert is None:
            logger.debug("Alert %s not found — returning empty knowledge context", alert_id)
            return ""
        return self.get_context_for_alert(alert, max_chunks, min_similarity)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_chunks(
        self,
        alert: Alert,
        max_chunks: int,
        min_similarity: float,
    ) -> List[dict]:
        """
        Fetch the most relevant DesignChunk records for *alert*.

        Uses pgvector cosine similarity when the alert has an embedding;
        falls back to ILIKE text search otherwise.

        Args:
            alert: Alert ORM object.
            max_chunks: Result limit.
            min_similarity: Minimum similarity threshold (vector search only).

        Returns:
            List of dicts with at least a ``content`` key.
        """
        app_id: Optional[UUID] = getattr(alert, "app_id", None)

        # --- Vector search path ---
        if getattr(alert, "embedding", None) is not None:
            return self._vector_search(alert.embedding, app_id, max_chunks, min_similarity)

        # --- Text search fallback ---
        return self._text_search(alert.alert_name, app_id, max_chunks)

    def _vector_search(
        self,
        embedding: List[float],
        app_id: Optional[UUID],
        limit: int,
        min_similarity: float,
    ) -> List[dict]:
        """
        Search DesignChunk via pgvector cosine similarity.

        Args:
            embedding: Query embedding vector.
            app_id: Optional application filter.
            limit: Maximum rows to return.
            min_similarity: Minimum similarity threshold.

        Returns:
            List of result dicts.
        """
        filters = ["c.embedding IS NOT NULL"]
        params: dict = {
            "query_embedding": embedding,
            "limit": limit,
            "min_similarity": min_similarity,
        }

        if app_id is not None:
            filters.append("c.app_id = :app_id")
            params["app_id"] = str(app_id)

        where = " AND ".join(filters)
        sql = text(
            f"""
            SELECT
                c.content,
                1 - (c.embedding <=> CAST(:query_embedding AS vector)) AS similarity
            FROM design_chunks c
            WHERE {where}
              AND 1 - (c.embedding <=> CAST(:query_embedding AS vector)) >= :min_similarity
            ORDER BY c.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :limit
            """
        )

        try:
            rows = self.db.execute(sql, params).fetchall()
            return [{"content": r.content, "similarity": float(r.similarity)} for r in rows]
        except Exception as exc:
            logger.warning("Vector search failed: %s", exc)
            return []

    def _text_search(
        self,
        query: str,
        app_id: Optional[UUID],
        limit: int,
    ) -> List[dict]:
        """
        ILIKE-based fallback when no alert embedding is available.

        Args:
            query: Alert name used as search term.
            app_id: Optional application filter.
            limit: Maximum rows to return.

        Returns:
            List of result dicts.
        """
        try:
            q = self.db.query(DesignChunk)
            if app_id is not None:
                q = q.filter(DesignChunk.app_id == app_id)
            q = q.filter(DesignChunk.content.ilike(f"%{query}%"))
            rows = q.limit(limit).all()
            return [{"content": r.content, "similarity": 0.5} for r in rows]
        except Exception as exc:
            logger.warning("Text search failed: %s", exc)
            return []

    def _fetch_image_descriptions(self, alert: Alert) -> str:
        """
        Fetch ai_description values from DesignImage for the alert's app.

        Args:
            alert: Alert ORM object.

        Returns:
            Newline-separated descriptions or empty string.
        """
        app_id: Optional[UUID] = getattr(alert, "app_id", None)
        if app_id is None:
            return ""

        try:
            images = (
                self.db.query(DesignImage)
                .filter(
                    DesignImage.app_id == app_id,
                    DesignImage.ai_description.isnot(None),
                )
                .limit(3)
                .all()
            )
            if not images:
                return ""
            return "\n".join(
                f"[{img.title}] {img.ai_description}" for img in images if img.ai_description
            )
        except Exception as exc:
            logger.warning("Image description fetch failed: %s", exc)
            return ""

    def _fetch_resolved_alerts(self, alert: Alert) -> str:
        """
        Fetch successfully resolved alerts with high embedding similarity.

        Returns a summary of past resolutions to inform the LLM.

        Args:
            alert: Alert ORM object.

        Returns:
            Formatted string of past resolutions or empty string.
        """
        # Try postmortem reports if available (Feature 4 guard)
        postmortem_context = self._fetch_postmortems(getattr(alert, "app_id", None))

        # Embedding-based resolved-alert search
        if getattr(alert, "embedding", None) is None:
            return postmortem_context

        try:
            params: dict = {
                "query_embedding": alert.embedding,
                "alert_id": str(alert.id),
                "limit": 3,
                "min_similarity": 0.7,
            }
            sql = text(
                """
                SELECT
                    a.alert_name,
                    a.ai_analysis,
                    1 - (a.embedding <=> CAST(:query_embedding AS vector)) AS similarity
                FROM alerts a
                WHERE a.id != :alert_id
                  AND a.embedding IS NOT NULL
                  AND a.status = 'resolved'
                  AND a.ai_analysis IS NOT NULL
                  AND 1 - (a.embedding <=> CAST(:query_embedding AS vector)) >= :min_similarity
                ORDER BY a.embedding <=> CAST(:query_embedding AS vector)
                LIMIT :limit
                """
            )
            rows = self.db.execute(sql, params).fetchall()
            if not rows:
                return postmortem_context

            lines = [
                f"- **{r.alert_name}** (similarity {float(r.similarity):.2f}): {r.ai_analysis[:200]}"
                for r in rows
            ]
            resolved_str = "\n".join(lines)
            if postmortem_context:
                return resolved_str + "\n\n" + postmortem_context
            return resolved_str

        except Exception as exc:
            logger.warning("Resolved alert search failed: %s", exc)
            return postmortem_context

    def _fetch_postmortems(self, app_id: Optional[UUID]) -> str:
        """
        Fetch past postmortem reports (Feature 4 guard — returns empty string
        if the PostmortemReport model is not yet present).

        Args:
            app_id: Application UUID to filter on.

        Returns:
            Formatted string or empty string.
        """
        if app_id is None:
            return ""
        try:
            from app.models_postmortem import PostmortemReport  # type: ignore[import]

            reports = (
                self.db.query(PostmortemReport)
                .filter(PostmortemReport.app_id == app_id)
                .order_by(PostmortemReport.created_at.desc())
                .limit(2)
                .all()
            )
            if not reports:
                return ""
            lines = [
                f"- Postmortem ({r.created_at.date()}): {(getattr(r, 'summary', None) or getattr(r, 'impact_summary', None) or '')[:200]}"
                for r in reports
                if getattr(r, 'summary', None) or getattr(r, 'impact_summary', None)
            ]
            return "\n".join(lines)
        except ImportError:
            # PostmortemReport not yet defined — silently skip
            return ""
        except Exception as exc:
            logger.warning("Postmortem fetch failed: %s", exc)
            return ""

    @staticmethod
    def _truncate(text: str) -> str:
        """
        Truncate *text* to approximately _MAX_TOKENS tokens.

        Args:
            text: Input string.

        Returns:
            String truncated to _MAX_CHARS characters (word boundary).
        """
        if len(text) <= _MAX_CHARS:
            return text
        truncated = text[:_MAX_CHARS]
        # Break at last newline to avoid mid-sentence cut
        last_newline = truncated.rfind("\n")
        if last_newline > _MAX_CHARS // 2:
            truncated = truncated[:last_newline]
        return truncated + "\n\n*[Context truncated for length]*"
