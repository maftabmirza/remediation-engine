"""
Feedback and Learning API Router
Endpoints for feedback collection, effectiveness scoring, and similar incident search
"""
import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import Alert, User, SolutionOutcome
from app.models_remediation import Runbook, RunbookExecution
from app.models_learning import AnalysisFeedback, ExecutionOutcome
from app.schemas_learning import (
    FeedbackCreate, FeedbackResponse,
    ExecutionOutcomeCreate, ExecutionOutcomeResponse,
    RunbookEffectiveness,
    SimilarIncidentsResponse,
    EmbeddingGenerationRequest, EmbeddingGenerationResponse
)
from app.services.effectiveness_service import EffectivenessService
from app.services.similarity_service import SimilarityService
from app.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Solution Feedback Endpoints (Learning System)
# ============================================================================

class SolutionFeedbackCreate(BaseModel):
    """Request body for solution feedback submission."""
    solution_type: str  # 'command', 'runbook', 'knowledge', 'agent_suggestion'
    solution_reference: str  # The command text, runbook id, etc.
    success: bool
    session_id: Optional[str] = None
    user_feedback: Optional[str] = None
    problem_description: Optional[str] = None


class SolutionFeedbackResponse(BaseModel):
    """Response for solution feedback submission."""
    id: str
    message: str


@router.post("/solution-feedback", response_model=SolutionFeedbackResponse, status_code=201)
async def submit_solution_feedback(
    feedback: SolutionFeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit feedback on whether a suggested solution worked.
    
    This enables the learning system to track what solutions work for which problems.
    """
    import uuid
    
    # Create solution outcome record
    outcome = SolutionOutcome(
        session_id=UUID(feedback.session_id) if feedback.session_id else None,
        problem_description=feedback.problem_description or f"User ran: {feedback.solution_reference}",
        solution_type=feedback.solution_type,
        solution_reference=feedback.solution_reference,
        solution_summary=feedback.solution_reference[:200] if feedback.solution_reference else None,
        success=feedback.success,
        auto_detected=False,  # User-provided feedback
        user_feedback=feedback.user_feedback,
        feedback_timestamp=datetime.now(timezone.utc)
    )
    
    db.add(outcome)
    db.commit()
    db.refresh(outcome)
    
    logger.info(f"User {current_user.username} submitted solution feedback: {feedback.solution_type} - {'success' if feedback.success else 'failed'}")
    
    return SolutionFeedbackResponse(
        id=str(outcome.id),
        message="Feedback recorded successfully"
    )


# ============================================================================
# Feedback Endpoints
# ============================================================================

@router.post("/alerts/{alert_id}/feedback", response_model=FeedbackResponse, status_code=201)
async def submit_analysis_feedback(
    alert_id: UUID,
    feedback: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit feedback on AI-generated alert analysis.
    
    Allows users to rate the quality and usefulness of AI recommendations.
    """
    # Verify alert exists
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Create feedback record
    feedback_record = AnalysisFeedback(
        alert_id=alert_id,
        user_id=current_user.id,
        helpful=feedback.helpful,
        rating=feedback.rating,
        accuracy=feedback.accuracy,
        what_was_missing=feedback.what_was_missing,
        what_actually_worked=feedback.what_actually_worked
    )
    
    db.add(feedback_record)
    db.commit()
    db.refresh(feedback_record)
    
    logger.info(f"User {current_user.username} submitted feedback for alert {alert_id}")
    
    return feedback_record


@router.get("/alerts/{alert_id}/feedback", response_model=List[FeedbackResponse])
async def get_alert_feedback(
    alert_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all feedback for a specific alert."""
    # Verify alert exists
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    feedback_records = (
        db.query(AnalysisFeedback)
        .filter(AnalysisFeedback.alert_id == alert_id)
        .order_by(AnalysisFeedback.created_at.desc())
        .all()
    )
    
    return feedback_records


# ============================================================================
# Execution Outcome Endpoints
# ============================================================================

@router.post("/executions/{execution_id}/outcome", response_model=ExecutionOutcomeResponse, status_code=201)
async def submit_execution_outcome(
    execution_id: UUID,
    outcome: ExecutionOutcomeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit outcome for a runbook execution.
    
    Tracks whether the execution resolved the issue and collects improvement suggestions.
    """
    # Verify execution exists
    execution = db.query(RunbookExecution).filter(RunbookExecution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    # Check if outcome already exists
    existing_outcome = (
        db.query(ExecutionOutcome)
        .filter(ExecutionOutcome.execution_id == execution_id)
        .first()
    )
    if existing_outcome:
        raise HTTPException(status_code=409, detail="Outcome already exists for this execution")
    
    # Create outcome record
    outcome_record = ExecutionOutcome(
        execution_id=execution_id,
        alert_id=execution.alert_id,
        user_id=current_user.id,
        resolved_issue=outcome.resolved_issue,
        resolution_type=outcome.resolution_type,
        time_to_resolution_minutes=outcome.time_to_resolution_minutes,
        recommendation_followed=outcome.recommendation_followed,
        manual_steps_taken=outcome.manual_steps_taken,
        improvement_suggestion=outcome.improvement_suggestion
    )
    
    db.add(outcome_record)
    db.commit()
    db.refresh(outcome_record)
    
    logger.info(f"User {current_user.username} submitted outcome for execution {execution_id}")
    
    return outcome_record


# ============================================================================
# Effectiveness Endpoints
# ============================================================================

@router.get("/runbooks/{runbook_id}/effectiveness", response_model=RunbookEffectiveness)
async def get_runbook_effectiveness(
    runbook_id: UUID,
    days_lookback: int = 90,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get effectiveness metrics for a runbook.
    
    Calculates overall score, success rate, average resolution time,
    and provides breakdown by alert type.
    """
    # Verify runbook exists
    runbook = db.query(Runbook).filter(Runbook.id == runbook_id).first()
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    # Calculate effectiveness
    effectiveness_service = EffectivenessService(db)
    effectiveness = effectiveness_service.calculate_runbook_effectiveness(
        runbook_id=runbook_id,
        days_lookback=days_lookback
    )
    
    if not effectiveness:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient data to calculate effectiveness. Need at least {effectiveness_service.MIN_EXECUTIONS_FOR_SCORE} executions with outcomes."
        )
    
    return effectiveness


# ============================================================================
# Similar Incidents Endpoints
# ============================================================================

@router.get("/alerts/{alert_id}/similar", response_model=SimilarIncidentsResponse)
async def get_similar_incidents(
    alert_id: UUID,
    limit: int = 5,
    min_similarity: float = 0.7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Find similar historical incidents using vector similarity.
    
    Returns alerts with similar characteristics that have been previously resolved,
    showing what worked in the past.
    """
    # Verify alert exists
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Find similar alerts
    similarity_service = SimilarityService(db)
    similar_incidents = similarity_service.find_similar_alerts(
        alert_id=alert_id,
        limit=limit,
        min_similarity=min_similarity
    )
    
    if not similar_incidents:
        # Return empty result if no similar incidents found
        return SimilarIncidentsResponse(
            alert_id=alert_id,
            similar_incidents=[],
            total_found=0
        )
    
    return similar_incidents


# ============================================================================
# Embedding Generation Endpoints (Admin only)
# ============================================================================

@router.post("/alerts/generate-embeddings", response_model=EmbeddingGenerationResponse)
async def generate_alert_embeddings(
    request: EmbeddingGenerationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate embeddings for alerts (background task).
    
    Admin only endpoint to batch process alerts and generate vector embeddings
    for similarity search. This is a potentially long-running operation.
    """
    # Check if user has admin role
    if current_user.role not in ['admin', 'engineer']:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Start background task
    import uuid
    task_id = str(uuid.uuid4())
    
    # Count alerts to process
    if request.force_regenerate:
        count = db.query(Alert).count()
        alerts_to_process = min(count, request.limit)
    else:
        count = db.query(Alert).filter(Alert.embedding.is_(None)).count()
        alerts_to_process = min(count, request.limit)
    
    # Add background task
    background_tasks.add_task(
        _generate_embeddings_task,
        db_session=db,
        limit=request.limit,
        force_regenerate=request.force_regenerate
    )
    
    logger.info(f"Started embedding generation task {task_id} for {alerts_to_process} alerts")
    
    return EmbeddingGenerationResponse(
        task_id=task_id,
        status="started",
        alerts_to_process=alerts_to_process,
        message=f"Processing {alerts_to_process} alerts in background"
    )


def _generate_embeddings_task(
    db_session: Session,
    limit: int,
    force_regenerate: bool
):
    """Background task to generate embeddings."""
    try:
        similarity_service = SimilarityService(db_session)
        processed = similarity_service.generate_missing_embeddings(
            limit=limit,
            force_regenerate=force_regenerate
        )
        logger.info(f"Embedding generation task completed: {processed} alerts processed")
    except Exception as e:
        logger.error(f"Embedding generation task failed: {e}")
