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


@router.post("/chat")
async def ai_helper_chat(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handle troubleshooting chat messages via REST API.
    
    This endpoint uses the NativeToolAgent for troubleshooting conversations
    with tool calling capabilities (run commands, analyze logs, etc.)
    """
    from app.models import LLMProvider
    from app.services.agentic.native_agent import NativeToolAgent
    
    message = request.get("message", "")
    session_id = request.get("session_id", "")
    
    logger.info(f"AI Helper chat from {current_user.username}: {message[:100]}...")
    
    try:
        # Get the default LLM provider
        provider = db.query(LLMProvider).filter(
            LLMProvider.is_default == True,
            LLMProvider.is_enabled == True
        ).first()
        
        if not provider:
            provider = db.query(LLMProvider).filter(
                LLMProvider.is_enabled == True
            ).first()
        
        if not provider:
            return {
                "response": "No LLM provider is configured. Please configure an LLM provider in Settings.",
                "message": "No LLM provider is configured. Please configure an LLM provider in Settings.",
                "session_id": session_id
            }
        
        # Create the Native Tool Agent for troubleshooting
        agent = NativeToolAgent(
            db=db,
            provider=provider,
            alert=None,  # No specific alert context
            max_iterations=5,
            temperature=0.3
        )
        
        # Use stream() to get CMD_CARD markers for command buttons
        # Collect all streamed chunks into a single response
        full_response = ""
        tool_calls = []
        
        async for chunk in agent.stream(message):
            full_response += chunk
        
        # Get tool calls made
        if hasattr(agent, 'tool_calls_made'):
            tool_calls = agent.tool_calls_made
        
        # Debug: Log the full response to verify CMD_CARD markers
        logger.info(f"AI Helper chat response length: {len(full_response)}")
        if "[CMD_CARD]" in full_response:
            logger.info("✅ CMD_CARD markers found in response")
        else:
            logger.warning("⚠️ No CMD_CARD markers in response")
        
        return {
            "response": full_response,
            "message": full_response,
            "session_id": session_id,
            "tool_calls": tool_calls
        }
        
    except Exception as e:
        logger.error(f"AI Helper chat failed: {e}", exc_info=True)
        return {
            "response": f"I apologize, but I encountered an error: {str(e)}",
            "message": f"I apologize, but I encountered an error: {str(e)}",
            "session_id": session_id
        }

