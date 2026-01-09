"""
AI Helper Widget API 

Simple alias router to support the AI Helper widget.
Routes to the observability query system.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
import logging

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models import User
from app.services.observability_orchestrator import get_observability_orchestrator
from app.services.query_response_formatter import get_response_formatter

router = APIRouter(
    prefix="/api/ai-helper",
    tags=["ai-helper"]
)

logger = logging.getLogger(__name__)


class AIHelperQueryRequest(BaseModel):
    query: str
    page_context: Optional[dict] = None
    session_id: Optional[str] = None


class AIHelperQueryResponse(BaseModel):
    response: str
    session_id: Optional[str] = None
    query_id: Optional[str] = None


@router.post("/query", response_model=AIHelperQueryResponse)
async def ai_helper_query(
    request: AIHelperQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handle AI Helper widget queries.
    
    Simple query endpoint for the floating AI assistant widget.
    Provides natural language responses using the observability orchestrator.
    """
    logger.info(f"AI Helper query from {current_user.username}: {request.query}")
    
    try:
        # Get orchestrator and execute query
        orchestrator = get_observability_orchestrator()
        result = await orchestrator.query(request.query)
        
        # Format response
        formatter = get_response_formatter()
        formatted = formatter.format(result)
        
        # Return simple text response for widget
        response_text = formatted.summary if hasattr(formatted, 'summary') and formatted.summary else "Query executed successfully."
        
        # Add insights if available
        if hasattr(formatted, 'insights') and formatted.insights:
            insights_text = "\n\n**Key Insights:**\n"
            for insight in formatted.insights[:3]:  # Limit to first 3
                # Handle both object attributes and dict access
                if hasattr(insight, 'message'):
                    msg = insight.message
                elif isinstance(insight, dict):
                    msg = insight.get('message', '')
                else:
                    msg = str(insight)
                insights_text += f"- {msg}\n"
            response_text += insights_text
        
        return AIHelperQueryResponse(
            response=response_text,
            session_id=request.session_id,
            query_id=str(result.original_query) if hasattr(result, 'original_query') else None
        )
        
    except Exception as e:
        logger.error(f"AI Helper query failed: {e}")
        return AIHelperQueryResponse(
            response=f"I apologize, but I encountered an error processing your query: {str(e)}",
            session_id=request.session_id
        )
