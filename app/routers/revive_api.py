"""
AI Helper Widget API 

Full-featured router to support the AI Helper widget.
Routes to the AI Helper Orchestrator for context-aware assistance.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models import User
from app.services.revive_orchestrator import get_revive_orchestrator
from app.schemas_revive import AIHelperQueryRequest, AIHelperQueryResponse

router = APIRouter(
    prefix="/api/ai-helper",
    tags=["ai-helper"]
)

logger = logging.getLogger(__name__)


@router.post("/query", response_model=AIHelperQueryResponse)
async def ai_helper_query(
    request: AIHelperQueryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handle AI Helper widget queries.
    
    Routes to the AI Orchestrator which determines intent (Observability vs Remediation)
    and executes the appropriate logic.
    """
    logger.info(f"AI Helper query from {current_user.username}: {request.query}")
    
    try:
        orchestrator = get_revive_orchestrator()
        
        # Execute query via orchestrator
        # Note: We await here because the orchestrator might do async IO (e.g. observability queries)
        result = await orchestrator.processed_query(
            db=db,
            query=request.query,
            user=current_user,
            session_id=request.session_id,
            context=request.page_context
        )
        
        return AIHelperQueryResponse(**result)
        
    except Exception as e:
        logger.error(f"AI Helper query failed: {e}", exc_info=True)
        return AIHelperQueryResponse(
            response=f"I apologize, but I encountered an error processing your query: {str(e)}",
            session_id=request.session_id,
            confidence=0.0
        )
