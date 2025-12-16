"""
Similarity Service
Finds similar historical alerts using vector embeddings and pgvector
"""
import logging
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

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
            
            # Build response
            similar_incidents = []
            for similar_alert, similarity_score in similar_alerts_query:
                # Get resolution info if available
                resolution_info = self._get_resolution_info(similar_alert.id)
                
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
    
    def _get_resolution_info(self, alert_id: UUID) -> Optional[ResolutionInfo]:
        """Get resolution information for an alert."""
        try:
            # Find the most recent successful execution for this alert
            execution_with_outcome = (
                self.db.query(RunbookExecution, ExecutionOutcome)
                .join(ExecutionOutcome, ExecutionOutcome.execution_id == RunbookExecution.id)
                .filter(
                    RunbookExecution.alert_id == alert_id,
                    RunbookExecution.status == 'success'
                )
                .order_by(RunbookExecution.completed_at.desc())
                .first()
            )
            
            if execution_with_outcome:
                execution, outcome = execution_with_outcome
                
                return ResolutionInfo(
                    method="runbook",
                    runbook_id=execution.runbook_id,
                    runbook_name=execution.runbook.name if execution.runbook else None,
                    success=outcome.resolved_issue or False,
                    time_minutes=outcome.time_to_resolution_minutes
                )
            
            # Check if there was a manual resolution (feedback without runbook execution)
            # This would require analyzing feedback data
            # For now, just return None if no runbook execution found
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting resolution info for alert {alert_id}: {e}")
            return None
    
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
