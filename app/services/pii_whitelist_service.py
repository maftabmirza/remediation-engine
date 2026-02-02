"""
Whitelist service for PII false positive management.

Manages user-reported false positives and provides whitelist checking
to prevent unnecessary PII detections.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pii_models import PIIFalsePositiveFeedback
from app.models import User
from app.schemas.pii_schemas import (
    FalsePositiveFeedbackRequest,
    FalsePositiveFeedbackResponse,
    FalsePositiveFeedbackDetail,
    FalsePositiveFeedbackListResponse,
    WhitelistEntry,
    WhitelistResponse
)

logger = logging.getLogger(__name__)


class PIIWhitelistService:
    """
    Service for managing PII false positive feedback and whitelist.
    
    Features:
    - Store user feedback on false positives
    - Maintain whitelist cache for performance
    - Check text against whitelist before detection
    - Support organization/user/global scopes
    """
    
    # Cache settings
    CACHE_TTL_SECONDS = 300  # 5 minutes
    MAX_CACHE_SIZE = 10000
    
    def __init__(self, db: AsyncSession):
        """Initialize whitelist service with database session."""
        self.db = db
        self._whitelist_cache: Dict[str, Set[str]] = {}
        self._cache_timestamp: Optional[datetime] = None
    
    async def submit_feedback(
        self,
        request: FalsePositiveFeedbackRequest,
        user_id: UUID
    ) -> FalsePositiveFeedbackResponse:
        """
        Submit false positive feedback from user.
        
        Args:
            request: Feedback request with detection details
            user_id: User submitting the feedback
            
        Returns:
            Response with feedback ID and status
        """
        # Check if already reported
        existing = await self.db.execute(
            select(PIIFalsePositiveFeedback).where(
                and_(
                    PIIFalsePositiveFeedback.detected_text == request.detected_text,
                    PIIFalsePositiveFeedback.user_id == user_id,
                    PIIFalsePositiveFeedback.whitelisted == True
                )
            )
        )
        existing_feedback = existing.scalar_one_or_none()
        
        if existing_feedback:
            logger.info(f"User {user_id} already reported '{request.detected_text}' as false positive")
            return FalsePositiveFeedbackResponse(
                id=existing_feedback.id,
                detected_text=existing_feedback.detected_text,
                detected_entity_type=existing_feedback.detected_entity_type,
                whitelisted=existing_feedback.whitelisted,
                review_status=existing_feedback.review_status,
                reported_at=existing_feedback.reported_at,
                message="This text is already whitelisted from your previous feedback."
            )
        
        # Create new feedback entry
        feedback = PIIFalsePositiveFeedback(
            detected_text=request.detected_text,
            detected_entity_type=request.detected_entity_type,
            detection_engine=request.detection_engine,
            original_confidence=request.original_confidence,
            user_id=user_id,
            session_id=request.session_id,
            agent_mode=request.agent_mode,
            detection_log_id=request.detection_log_id,
            user_comment=request.user_comment,
            whitelisted=True,
            whitelisted_at=datetime.utcnow(),
            whitelist_scope='organization',  # Default scope
            review_status='auto_approved'  # Auto-approve by default
        )
        
        self.db.add(feedback)
        await self.db.commit()
        await self.db.refresh(feedback)
        
        # Invalidate cache
        self._cache_timestamp = None
        
        logger.info(
            f"False positive feedback submitted: text='{request.detected_text[:30]}...', "
            f"entity={request.detected_entity_type}, user={user_id}"
        )
        
        return FalsePositiveFeedbackResponse(
            id=feedback.id,
            detected_text=feedback.detected_text,
            detected_entity_type=feedback.detected_entity_type,
            whitelisted=feedback.whitelisted,
            review_status=feedback.review_status,
            reported_at=feedback.reported_at,
            message="Feedback submitted successfully. This text will no longer be flagged."
        )
    
    async def is_whitelisted(
        self,
        text: str,
        entity_type: Optional[str] = None,
        scope: str = 'organization'
    ) -> bool:
        """
        Check if text is in whitelist.
        
        Args:
            text: Text to check
            entity_type: Optional entity type filter
            scope: Whitelist scope to check
            
        Returns:
            True if whitelisted, False otherwise
        """
        # Ensure cache is loaded
        await self._ensure_cache_loaded()
        
        # Check cache
        cache_key = f"{scope}:{entity_type or 'ANY'}"
        logger.debug(f"🔍 Checking whitelist: text='{text[:30]}...', cache_key='{cache_key}'")
        
        if cache_key in self._whitelist_cache:
            is_in_whitelist = text in self._whitelist_cache[cache_key]
            if is_in_whitelist:
                logger.info(f"✅ Whitelist match found for '{text[:30]}...' in cache_key '{cache_key}'")
            else:
                logger.debug(f"❌ Text '{text[:30]}...' not found in whitelist cache_key '{cache_key}' ({len(self._whitelist_cache[cache_key])} entries)")
            return is_in_whitelist
        else:
            logger.debug(f"❌ Cache key '{cache_key}' not found in whitelist. Available keys: {list(self._whitelist_cache.keys())}")
        
        return False
    
    async def get_whitelist(
        self,
        scope: Optional[str] = None,
        entity_type: Optional[str] = None,
        active_only: bool = True
    ) -> WhitelistResponse:
        """
        Get all whitelisted items.
        
        Args:
            scope: Filter by scope (organization/user/global)
            entity_type: Filter by entity type
            active_only: Only return active whitelist entries
            
        Returns:
            List of whitelist entries
        """
        query = select(PIIFalsePositiveFeedback, User).join(
            User,
            PIIFalsePositiveFeedback.user_id == User.id
        )
        
        conditions = []
        if active_only:
            conditions.append(PIIFalsePositiveFeedback.whitelisted == True)
        if scope:
            conditions.append(PIIFalsePositiveFeedback.whitelist_scope == scope)
        if entity_type:
            conditions.append(PIIFalsePositiveFeedback.detected_entity_type == entity_type)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(PIIFalsePositiveFeedback.reported_at.desc())
        
        result = await self.db.execute(query)
        rows = result.all()
        
        items = [
            WhitelistEntry(
                id=feedback.id,
                text=feedback.detected_text,
                entity_type=feedback.detected_entity_type,
                scope=feedback.whitelist_scope,
                added_at=feedback.whitelisted_at,
                added_by=feedback.user_id,
                reported_by=user.username if user else None,
                session_id=feedback.session_id,
                active=feedback.whitelisted
            )
            for feedback, user in rows
        ]
        
        return WhitelistResponse(
            items=items,
            total=len(items)
        )
    
    async def get_feedback_list(
        self,
        page: int = 1,
        limit: int = 50,
        user_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
        review_status: Optional[str] = None
    ) -> FalsePositiveFeedbackListResponse:
        """
        Get paginated list of feedback entries.
        
        Args:
            page: Page number (1-indexed)
            limit: Items per page
            user_id: Filter by user
            entity_type: Filter by entity type
            review_status: Filter by review status
            
        Returns:
            Paginated list of feedback
        """
        # Build query
        query = select(PIIFalsePositiveFeedback)
        count_query = select(func.count(PIIFalsePositiveFeedback.id))
        
        conditions = []
        if user_id:
            conditions.append(PIIFalsePositiveFeedback.user_id == user_id)
        if entity_type:
            conditions.append(PIIFalsePositiveFeedback.detected_entity_type == entity_type)
        if review_status:
            conditions.append(PIIFalsePositiveFeedback.review_status == review_status)
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        # Get paginated results
        query = query.order_by(PIIFalsePositiveFeedback.reported_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)
        
        result = await self.db.execute(query)
        feedbacks = result.scalars().all()
        
        items = [
            FalsePositiveFeedbackDetail(
                id=f.id,
                detected_text=f.detected_text,
                detected_entity_type=f.detected_entity_type,
                detection_engine=f.detection_engine,
                original_confidence=f.original_confidence,
                user_id=f.user_id,
                session_id=f.session_id,
                agent_mode=f.agent_mode,
                reported_at=f.reported_at,
                user_comment=f.user_comment,
                whitelisted=f.whitelisted,
                whitelisted_at=f.whitelisted_at,
                whitelist_scope=f.whitelist_scope,
                review_status=f.review_status,
                reviewed_by=f.reviewed_by,
                reviewed_at=f.reviewed_at,
                review_notes=f.review_notes,
                created_at=f.created_at,
                updated_at=f.updated_at
            )
            for f in feedbacks
        ]
        
        pages = (total + limit - 1) // limit
        
        return FalsePositiveFeedbackListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=pages
        )
    
    async def update_whitelist_status(
        self,
        feedback_id: UUID,
        whitelisted: bool,
        reviewer_id: UUID,
        review_notes: Optional[str] = None
    ) -> bool:
        """
        Update whitelist status (admin function).
        
        Args:
            feedback_id: Feedback entry ID
            whitelisted: New whitelist status
            reviewer_id: Admin user ID
            review_notes: Optional notes
            
        Returns:
            True if successful
        """
        result = await self.db.execute(
            select(PIIFalsePositiveFeedback).where(
                PIIFalsePositiveFeedback.id == feedback_id
            )
        )
        feedback = result.scalar_one_or_none()
        
        if not feedback:
            return False
        
        feedback.whitelisted = whitelisted
        feedback.reviewed_by = reviewer_id
        feedback.reviewed_at = datetime.utcnow()
        feedback.review_status = 'approved' if whitelisted else 'rejected'
        feedback.review_notes = review_notes
        
        await self.db.commit()
        
        # Invalidate cache
        self._cache_timestamp = None
        
        logger.info(f"Whitelist status updated for feedback {feedback_id}: whitelisted={whitelisted}")
        
        return True
    
    async def _ensure_cache_loaded(self):
        """Load whitelist into cache if needed."""
        now = datetime.utcnow()
        
        # Check if cache is valid
        if self._cache_timestamp:
            age = (now - self._cache_timestamp).total_seconds()
            if age < self.CACHE_TTL_SECONDS:
                logger.debug(f"PII whitelist cache is still valid (age: {age:.1f}s, TTL: {self.CACHE_TTL_SECONDS}s)")
                return  # Cache is still valid
        
        # Reload cache
        logger.info("🔄 Reloading PII whitelist cache from database")
        
        result = await self.db.execute(
            select(PIIFalsePositiveFeedback).where(
                PIIFalsePositiveFeedback.whitelisted == True
            )
        )
        feedbacks = result.scalars().all()
        
        logger.info(f"📊 Found {len(feedbacks)} whitelisted entries in database")
        
        # Build cache by scope and entity type
        self._whitelist_cache = {}
        
        for feedback in feedbacks:
            # Add to scope-specific cache
            cache_key = f"{feedback.whitelist_scope}:{feedback.detected_entity_type}"
            if cache_key not in self._whitelist_cache:
                self._whitelist_cache[cache_key] = set()
            self._whitelist_cache[cache_key].add(feedback.detected_text)
            
            # Also add to "ANY" entity type cache
            any_key = f"{feedback.whitelist_scope}:ANY"
            if any_key not in self._whitelist_cache:
                self._whitelist_cache[any_key] = set()
            self._whitelist_cache[any_key].add(feedback.detected_text)
            
            logger.debug(f"  Added to whitelist: '{feedback.detected_text[:30]}...' (scope={feedback.whitelist_scope}, type={feedback.detected_entity_type})")
        
        self._cache_timestamp = now
        
        total_entries = sum(len(entries) for entries in self._whitelist_cache.values())
        logger.info(f"✅ PII whitelist cache loaded: {total_entries} entries across {len(self._whitelist_cache)} categories")
        
        # Log cache keys for debugging
        logger.debug(f"Cache keys: {list(self._whitelist_cache.keys())}")
    
    def clear_cache(self):
        """Manually clear the whitelist cache."""
        self._whitelist_cache = {}
        self._cache_timestamp = None
        logger.info("PII whitelist cache cleared")
