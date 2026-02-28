"""
Similarity Service
Finds similar historical alerts using vector embeddings and pgvector
"""
import logging
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models import Alert
from app.models_remediation import RunbookExecution
from app.models_learning import ExecutionOutcome
from app.schemas_learning import SimilarIncident, SimilarIncidentsResponse, ResolutionInfo

logger = logging.getLogger(__name__)


class SimilarityService:
    """Service for finding similar historical alerts using vector similarity."""
    
    DEFAULT_SIMILARITY_THRESHOLD = 0.7  # Minimum cosine similarity to include
    DEFAULT_LIMIT = 5  # Number of similar incidents to return
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_similar_alerts(
        self,
        alert_id: UUID,
        limit: int = DEFAULT_LIMIT,
        min_similarity: float = DEFAULT_SIMILARITY_THRESHOLD
    ) -> Optional[SimilarIncidentsResponse]:
        """
        Find similar historical alerts using cosine similarity.
        
        Args:
            alert_id: UUID of the alert to find similar incidents for
            limit: Maximum number of similar incidents to return
            min_similarity: Minimum similarity score (0.0-1.0)
            
        Returns:
            SimilarIncidentsResponse or None if alert not found or has no embedding
        """
        try:
            # Get the target alert
            alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
            if not alert:
                logger.error(f"Alert {alert_id} not found")
                return None
            
            if not alert.embedding:
                logger.warning(f"Alert {alert_id} has no embedding - cannot find similar alerts")
                return None
            
            # Find similar alerts using pgvector's cosine similarity
            # Use ORDER BY embedding <=> target_embedding for cosine distance
            # Cosine distance = 1 - cosine_similarity, so we convert back to similarity
            similar_alerts_query = (
                self.db.query(
                    Alert,
                    # Calculate cosine similarity (1 - cosine distance)
                    (1 - Alert.embedding.cosine_distance(alert.embedding)).label('similarity')
                )
                .filter(
                    Alert.id != alert_id,  # Exclude the alert itself
                    Alert.embedding.isnot(None),  # Must have embedding
                    # Filter for minimum similarity (converted to max distance)
                    Alert.embedding.cosine_distance(alert.embedding) <= (1 - min_similarity)
                )
                .order_by(Alert.embedding.cosine_distance(alert.embedding))
                .limit(limit)
                .all()
            )
            
            # Build response — fetch all resolution info in one bulk query to avoid N+1
            similar_alert_ids = [sa.id for sa, _ in similar_alerts_query]
            resolution_map = self._get_resolution_info_bulk(similar_alert_ids)

            similar_incidents = []
            for similar_alert, similarity_score in similar_alerts_query:
                resolution_info = resolution_map.get(similar_alert.id)

                similar_incidents.append(SimilarIncident(
                    alert_id=similar_alert.id,
                    alert_name=similar_alert.alert_name,
                    similarity_score=round(float(similarity_score), 4),
                    occurred_at=similar_alert.timestamp,
                    severity=similar_alert.severity,
                    instance=similar_alert.instance,
                    resolution=resolution_info
                ))
            
            return SimilarIncidentsResponse(
                alert_id=alert_id,
                similar_incidents=similar_incidents,
                total_found=len(similar_incidents)
            )
            
        except Exception as e:
            logger.error(f"Error finding similar alerts for {alert_id}: {e}")
            return None
    
    def _get_resolution_info_bulk(self, alert_ids: list) -> dict:
        """
        Get resolution information for multiple alerts in a single query.
        Avoids the N+1 pattern of calling _get_resolution_info() inside a loop.
        Returns a dict mapping alert_id -> ResolutionInfo.
        """
        if not alert_ids:
            return {}

        try:
            from app.models_remediation import Runbook

            # Subquery: latest successful completed_at per alert
            subq = (
                self.db.query(
                    RunbookExecution.alert_id,
                    func.max(RunbookExecution.completed_at).label('max_completed_at')
                )
                .filter(
                    RunbookExecution.alert_id.in_(alert_ids),
                    RunbookExecution.status == 'success'
                )
                .group_by(RunbookExecution.alert_id)
                .subquery()
            )

            rows = (
                self.db.query(RunbookExecution, ExecutionOutcome, Runbook)
                .join(ExecutionOutcome, ExecutionOutcome.execution_id == RunbookExecution.id)
                .outerjoin(Runbook, Runbook.id == RunbookExecution.runbook_id)
                .join(
                    subq,
                    and_(
                        RunbookExecution.alert_id == subq.c.alert_id,
                        RunbookExecution.completed_at == subq.c.max_completed_at,
                    )
                )
                .all()
            )

            return {
                execution.alert_id: ResolutionInfo(
                    method="runbook",
                    runbook_id=execution.runbook_id,
                    runbook_name=runbook.name if runbook else None,
                    success=outcome.resolved_issue or False,
                    time_minutes=outcome.time_to_resolution_minutes,
                )
                for execution, outcome, runbook in rows
            }

        except Exception as e:
            logger.error(f"Error getting bulk resolution info: {e}")
            return {}

    def _get_resolution_info(self, alert_id: UUID) -> Optional[ResolutionInfo]:
        """Get resolution information for a single alert (used outside bulk context)."""
        result = self._get_resolution_info_bulk([alert_id])
        return result.get(alert_id)
    
    def generate_missing_embeddings(
        self,
        limit: int = 100,
        force_regenerate: bool = False
    ) -> int:
        """
        Generate embeddings for alerts that don't have them.
        
        Args:
            limit: Maximum number of alerts to process
            force_regenerate: If True, regenerate embeddings even if they exist
            
        Returns:
            Number of alerts processed
        """
        try:
            from app.services.embedding_service import EmbeddingService
            
            embedding_service = EmbeddingService()
            
            if not embedding_service.is_configured():
                logger.error("Embedding service not configured - cannot generate embeddings")
                return 0
            
            # Get alerts without embeddings (or all if force_regenerate)
            if force_regenerate:
                alerts_query = self.db.query(Alert).limit(limit)
            else:
                alerts_query = (
                    self.db.query(Alert)
                    .filter(Alert.embedding.is_(None))
                    .limit(limit)
                )
            
            alerts = alerts_query.all()
            
            if not alerts:
                logger.info("No alerts need embedding generation")
                return 0
            
            processed_count = 0
            for alert in alerts:
                try:
                    # Generate embedding
                    embedding = embedding_service.generate_for_alert(alert)
                    
                    if embedding:
                        # Build embedding text for reference
                        parts = [
                            f"Alert: {alert.alert_name}",
                            f"Severity: {alert.severity or 'unknown'}",
                        ]
                        if alert.instance:
                            parts.append(f"Instance: {alert.instance}")
                        embedding_text = ', '.join(parts)
                        
                        # Update alert with embedding
                        alert.embedding = embedding
                        alert.embedding_text = embedding_text
                        
                        processed_count += 1
                    else:
                        logger.warning(f"Failed to generate embedding for alert {alert.id}")
                        
                except Exception as e:
                    logger.error(f"Error processing alert {alert.id}: {e}")
                    continue
            
            # Commit changes
            self.db.commit()
            
            logger.info(f"Generated embeddings for {processed_count} alerts")
            return processed_count
            
        except Exception as e:
            logger.error(f"Error in batch embedding generation: {e}")
            self.db.rollback()
            return 0
