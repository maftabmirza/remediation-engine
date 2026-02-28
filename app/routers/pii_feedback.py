"""
API endpoints for PII false positive feedback and whitelist management.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.services.auth_service import get_current_user, require_permission
from app.services.pii_whitelist_service import PIIWhitelistService
from app.models import User
from app.schemas.pii_schemas import (
    FalsePositiveFeedbackRequest,
    FalsePositiveFeedbackResponse,
    FalsePositiveFeedbackListResponse,
    WhitelistResponse,
    WhitelistUpdateRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/pii/feedback",
    tags=["PII Feedback"]
)


@router.post("/false-positive", response_model=FalsePositiveFeedbackResponse)
async def submit_false_positive_feedback(
    request: FalsePositiveFeedbackRequest,
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_permission(["pii_report_false_positive"])),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Submit feedback that a PII detection was a false positive.
    
    The reported text will be added to the whitelist and will no longer
    trigger PII detection in future scans.
    
    **Rate Limit:** 50 submissions per user per day
    """
    try:
        service = PIIWhitelistService(db)
        
        # TODO: Add rate limiting check here
        # Example: Check if user has submitted > 50 in last 24 hours
        
        response = await service.submit_feedback(
            request=request,
            user_id=current_user.id
        )
        
        logger.info(
            f"False positive feedback submitted by user {current_user.username}: "
            f"text='{request.detected_text[:30]}...', entity={request.detected_entity_type}"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error submitting false positive feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback. Please try again."
        )


@router.get("/whitelist", response_model=WhitelistResponse)
async def get_whitelist(
    scope: Optional[str] = Query(None, description="Filter by scope: organization/user/global"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    active_only: bool = Query(True, description="Only return active whitelist entries"),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_permission(["pii_view_config"])),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get the current whitelist of false positives.
    
    Returns all whitelisted items that are currently active.
    """
    try:
        service = PIIWhitelistService(db)
        
        response = await service.get_whitelist(
            scope=scope,
            entity_type=entity_type,
            active_only=active_only
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error retrieving whitelist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve whitelist"
        )


@router.get("/reports", response_model=FalsePositiveFeedbackListResponse)
async def get_feedback_reports(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=1000, description="Items per page"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    review_status: Optional[str] = Query(None, description="Filter by review status"),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_permission(["pii_read_logs"])),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get feedback reports.
    
    Regular users see only their own feedback.
    Admins can see all feedback reports.
    """
    try:
        service = PIIWhitelistService(db)
        
        # Regular users only see their own feedback
        admin_roles = {"admin", "owner", "security_admin"}
        user_filter = current_user.id if current_user.role not in admin_roles else None
        
        response = await service.get_feedback_list(
            page=page,
            limit=limit,
            user_id=user_filter,
            entity_type=entity_type,
            review_status=review_status
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error retrieving feedback reports: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve feedback reports"
        )


@router.put("/{feedback_id}/whitelist", response_model=dict)
async def update_whitelist_entry(
    feedback_id: UUID,
    request: WhitelistUpdateRequest,
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_permission(["pii_edit_config"])),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Update whitelist status for a feedback entry (Admin only).
    
    Admins can enable/disable whitelist entries or add review notes.
    """
    try:
        service = PIIWhitelistService(db)
        
        success = await service.update_whitelist_status(
            feedback_id=feedback_id,
            whitelisted=request.whitelisted,
            reviewer_id=current_user.id,
            review_notes=request.review_notes
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback entry not found"
            )
        
        logger.info(
            f"Whitelist entry {feedback_id} updated by admin {current_user.username}: "
            f"whitelisted={request.whitelisted}"
        )
        
        return {
            "message": "Whitelist entry updated successfully",
            "feedback_id": str(feedback_id),
            "whitelisted": request.whitelisted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating whitelist entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update whitelist entry"
        )


@router.delete("/{feedback_id}", response_model=dict)
async def delete_feedback_entry(
    feedback_id: UUID,
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_permission(["pii_edit_config"])),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Delete a feedback entry (Admin only).
    
    This permanently removes the entry from the database.
    """
    try:
        from app.models.pii_models import PIIFalsePositiveFeedback
        from sqlalchemy import select
        
        result = await db.execute(
            select(PIIFalsePositiveFeedback).where(
                PIIFalsePositiveFeedback.id == feedback_id
            )
        )
        feedback = result.scalar_one_or_none()
        
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback entry not found"
            )
        
        await db.delete(feedback)
        await db.commit()
        
        # Clear cache
        service = PIIWhitelistService(db)
        service.clear_cache()
        
        logger.info(f"Feedback entry {feedback_id} deleted by admin {current_user.username}")
        
        return {
            "message": "Feedback entry deleted successfully",
            "feedback_id": str(feedback_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting feedback entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete feedback entry"
        )
