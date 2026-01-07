"""
AI Helper API Router
Endpoints for AI helper with strict security enforcement
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models import User
from app.models_ai_helper import KnowledgeSource, AIHelperAuditLog
from app.models_learning import RunbookClick, AIFeedback
from app.schemas_ai_helper import (
    AIHelperQuery,
    AIHelperResponse,
    AIHelperApproval,
    AIHelperFeedback,
    KnowledgeSourceCreate,
    KnowledgeSourceUpdate,
    KnowledgeSourceResponse,
    KnowledgeSyncHistoryResponse,
    TriggerSyncRequest,
    AIAuditLogResponse,
    AIHelperAnalytics,
    AIHelperConfigResponse,
    AIHelperConfigUpdate,
    SolutionChoiceRequest,
    FeedbackRequest
)
from app.services.ai_helper_orchestrator import AIHelperOrchestrator
from app.services.ai_audit_service import AIAuditService
from app.services.knowledge_git_sync_service import KnowledgeGitSyncService
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/ai-helper", tags=["AI Helper"])


# ============================================================================
# AI HELPER INTERACTION ENDPOINTS
# ============================================================================

@router.post("/query", response_model=AIHelperResponse)
async def process_ai_query(
    request: Request,
    query: AIHelperQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process AI helper query
    SECURITY: User authentication required, all actions logged
    """
    try:
        # Security check: Block if request has AI helper header
        # (prevents AI from calling itself)
        if request.headers.get("X-AI-Helper-Request"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AI helper cannot make recursive calls"
            )

        orchestrator = AIHelperOrchestrator(db)

        response = await orchestrator.process_query(
            user_id=current_user.id,
            query=query.query,
            session_id=query.session_id,
            page_context=query.page_context,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent")
        )

        return response

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )


@router.post("/approval")
async def submit_approval(
    approval: AIHelperApproval,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit user approval/rejection of AI suggestion
    CRITICAL: Logs user decision
    """
    try:
        audit_service = AIAuditService(db)

        await audit_service.log_user_response(
            audit_log_id=approval.query_id,
            user_action=approval.action.value,
            modifications=approval.modifications,
            feedback_comment=approval.feedback
        )

        return {"status": "success", "message": "Approval recorded"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record approval: {str(e)}"
        )





@router.post("/track-choice")
async def track_solution_choice(
    request: SolutionChoiceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Track which solution the user chose.
    Updates ai_helper_audit_logs.user_modifications.
    
    Supports two modes:
    - audit_log_id: Direct reference to specific audit log
    - session_id: Chat session ID - finds most recent audit log for that session
    """
    audit_log = None
    
    if request.audit_log_id:
        # Direct audit log lookup
        audit_log = db.query(AIHelperAuditLog).filter(
            AIHelperAuditLog.id == request.audit_log_id
        ).first()
    elif request.session_id:
        # Session-based lookup: find most recent audit log for this session
        audit_log = db.query(AIHelperAuditLog).filter(
            AIHelperAuditLog.session_id == request.session_id,
            AIHelperAuditLog.user_id == current_user.id
        ).order_by(AIHelperAuditLog.timestamp.desc()).first()

    if not audit_log:
        # No audit log found - still track the click in runbook_clicks
        pass
    
    # Always save to runbook_clicks table for analytics
    if request.choice_data.solution_chosen_id and request.choice_data.solution_chosen_type == 'runbook':
        try:
            from uuid import UUID as UUIDtype
            runbook_uuid = UUIDtype(request.choice_data.solution_chosen_id)
            
            click_record = RunbookClick(
                runbook_id=runbook_uuid,
                user_id=current_user.id,
                session_id=request.session_id,
                source=request.source or 'unknown',
                query_text=None,  # Could extract from audit_log if available
                confidence_shown=None,
                rank_shown=request.choice_data.solution_chosen_rank,
                context_json={'user_action': request.choice_data.user_action}
            )
            db.add(click_record)
            db.commit()
        except Exception as e:
            # Don't fail the request if click tracking fails
            import logging
            logging.getLogger(__name__).warning(f"Failed to save runbook click: {e}")
    
    if not audit_log:
        return {"status": "tracked_anonymous", "message": "Click recorded to analytics"}

    # Update user_modifications field
    modifications = audit_log.user_modifications or {}
    
    # Merge existing modifications with new choice data
    choice_dict = request.choice_data.dict()
    choice_dict['chosen_at'] = datetime.utcnow().isoformat()
    
    # Calculate time to decision if timestamp available
    if audit_log.timestamp:
        # Ensure current time is timezone-aware if audit_log.timestamp is
        current_time = datetime.now(timezone.utc)
        
        # Handle naive/aware mismatch
        if audit_log.timestamp.tzinfo is None:
            current_time = datetime.utcnow()
            
        choice_dict['time_to_decision_seconds'] = (
            current_time - audit_log.timestamp
        ).total_seconds()

    modifications.update(choice_dict)
    audit_log.user_modifications = modifications
    flag_modified(audit_log, "user_modifications")

    # Update user action if not already set or more specific
    if request.choice_data.user_action:
        audit_log.user_action = request.choice_data.user_action
    
    db.commit()

    return {"status": "tracked", "audit_log_id": str(audit_log.id)}


@router.post("/feedback")
async def submit_feedback(
    feedback_data: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Log user feedback (thumbs up/down) for runbooks or LLM responses.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Validate at least one ID is present
    if not feedback_data.runbook_id and not feedback_data.message_id:
        raise HTTPException(
            status_code=400, 
            detail="Either runbook_id or message_id must be provided"
        )
    
    try:
        feedback = AIFeedback(
            user_id=current_user.id,
            session_id=feedback_data.session_id,
            runbook_id=feedback_data.runbook_id,
            message_id=feedback_data.message_id,
            feedback_type=feedback_data.feedback_type,
            target_type=feedback_data.target_type,
            query_text=feedback_data.query_text,
            response_text=feedback_data.response_text
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        
        return {
            "status": "feedback_recorded",
            "feedback_id": str(feedback.id),
            "target_type": feedback_data.target_type,
            "feedback_type": feedback_data.feedback_type
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save feedback")




# ============================================================================
# AUDIT & ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/history", response_model=List[AIAuditLogResponse])
async def get_user_history(
    limit: int = 100,
    offset: int = 0,
    session_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's AI interaction history
    """
    try:
        audit_service = AIAuditService(db)
        history = await audit_service.get_user_history(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            session_id=session_id
        )
        return history

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get history: {str(e)}"
        )


@router.get("/analytics", response_model=AIHelperAnalytics)
async def get_analytics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get AI helper usage analytics
    """
    try:
        audit_service = AIAuditService(db)
        analytics = await audit_service.get_analytics(
            start_date=start_date,
            end_date=end_date,
            user_id=current_user.id
        )
        return analytics

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics: {str(e)}"
        )


# ============================================================================
# KNOWLEDGE SOURCE MANAGEMENT (ADMIN)
# ============================================================================

@router.get("/knowledge-sources", response_model=List[KnowledgeSourceResponse])
async def list_knowledge_sources(
    enabled_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all knowledge sources
    """
    # TODO: Add permission check for admin
    query = db.query(KnowledgeSource)

    if enabled_only:
        query = query.filter(KnowledgeSource.enabled == True)

    sources = query.all()
    return [KnowledgeSourceResponse.from_orm(source) for source in sources]


@router.post("/knowledge-sources", response_model=KnowledgeSourceResponse)
async def create_knowledge_source(
    source: KnowledgeSourceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new knowledge source
    ADMIN ONLY
    """
    # TODO: Add permission check for admin
    try:
        new_source = KnowledgeSource(
            name=source.name,
            description=source.description,
            source_type=source.source_type.value,
            config=source.config,
            enabled=source.enabled,
            sync_schedule=source.sync_schedule,
            auto_sync=source.auto_sync,
            created_by=current_user.id
        )

        db.add(new_source)
        db.commit()
        db.refresh(new_source)

        return KnowledgeSourceResponse.from_orm(new_source)

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create knowledge source: {str(e)}"
        )


@router.patch("/knowledge-sources/{source_id}", response_model=KnowledgeSourceResponse)
async def update_knowledge_source(
    source_id: UUID,
    update: KnowledgeSourceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update knowledge source
    ADMIN ONLY
    """
    # TODO: Add permission check for admin
    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.id == source_id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found"
        )

    try:
        # Update fields
        if update.name is not None:
            source.name = update.name
        if update.description is not None:
            source.description = update.description
        if update.config is not None:
            source.config = update.config
        if update.enabled is not None:
            source.enabled = update.enabled
        if update.sync_schedule is not None:
            source.sync_schedule = update.sync_schedule
        if update.auto_sync is not None:
            source.auto_sync = update.auto_sync
        if update.status is not None:
            source.status = update.status.value

        db.commit()
        db.refresh(source)

        return KnowledgeSourceResponse.from_orm(source)

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update knowledge source: {str(e)}"
        )


@router.delete("/knowledge-sources/{source_id}")
async def delete_knowledge_source(
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete knowledge source
    ADMIN ONLY
    """
    # TODO: Add permission check for admin
    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.id == source_id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found"
        )

    try:
        db.delete(source)
        db.commit()
        return {"status": "success", "message": "Knowledge source deleted"}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete knowledge source: {str(e)}"
        )


@router.post("/knowledge-sources/{source_id}/sync")
async def trigger_sync(
    source_id: UUID,
    sync_request: TriggerSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Trigger manual synchronization
    ADMIN ONLY
    """
    # TODO: Add permission check for admin
    try:
        sync_service = KnowledgeGitSyncService(db)
        stats = await sync_service.sync_source(source_id)

        return {
            "status": "success",
            "message": "Synchronization completed",
            "stats": stats
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Synchronization failed: {str(e)}"
        )


@router.get("/knowledge-sources/{source_id}/sync-history", response_model=List[KnowledgeSyncHistoryResponse])
async def get_sync_history(
    source_id: UUID,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get synchronization history for a source
    """
    from app.models_ai_helper import KnowledgeSyncHistory

    history = db.query(KnowledgeSyncHistory).filter(
        KnowledgeSyncHistory.source_id == source_id
    ).order_by(
        KnowledgeSyncHistory.created_at.desc()
    ).limit(limit).all()

    return [KnowledgeSyncHistoryResponse.from_orm(h) for h in history]


@router.post("/knowledge-sources/{source_id}/test")
async def test_source_connection(
    source_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test connection to knowledge source
    ADMIN ONLY
    """
    # TODO: Add permission check for admin
    source = db.query(KnowledgeSource).filter(
        KnowledgeSource.id == source_id
    ).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found"
        )

    try:
        sync_service = KnowledgeGitSyncService(db)
        result = await sync_service.test_connection(source)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection test failed: {str(e)}"
        )


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.get("/admin/blocked-actions", response_model=List[AIAuditLogResponse])
async def get_blocked_actions(
    days: int = 7,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of blocked actions (security monitoring)
    ADMIN ONLY
    """
    # TODO: Add permission check for admin
    try:
        audit_service = AIAuditService(db)
        start_date = datetime.utcnow() - timedelta(days=days)
        blocked = await audit_service.get_blocked_actions(
            start_date=start_date,
            limit=limit
        )
        return blocked

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get blocked actions: {str(e)}"
        )


@router.get("/admin/audit-report")
async def generate_audit_report(
    start_date: datetime,
    end_date: datetime,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate compliance audit report
    ADMIN ONLY
    """
    # TODO: Add permission check for admin
    try:
        audit_service = AIAuditService(db)
        report = await audit_service.generate_audit_report(
            start_date=start_date,
            end_date=end_date
        )
        return report

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}"
        )


@router.get("/admin/config", response_model=List[AIHelperConfigResponse])
async def get_ai_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get AI helper configuration
    ADMIN ONLY
    """
    # TODO: Add permission check for admin
    from app.models_ai_helper import AIHelperConfig

    configs = db.query(AIHelperConfig).all()
    return [AIHelperConfigResponse.from_orm(config) for config in configs]


@router.patch("/admin/config/{config_key}")
async def update_ai_config(
    config_key: str,
    update: AIHelperConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update AI helper configuration
    ADMIN ONLY
    """
    # TODO: Add permission check for admin
    from app.models_ai_helper import AIHelperConfig

    config = db.query(AIHelperConfig).filter(
        AIHelperConfig.config_key == config_key
    ).first()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )

    try:
        config.config_value = update.config_value
        if update.enabled is not None:
            config.enabled = update.enabled
        config.updated_by = current_user.id

        db.commit()
        db.refresh(config)

        return AIHelperConfigResponse.from_orm(config)

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {str(e)}"
        )
