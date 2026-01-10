"""
Troubleshooting API Router

Dedicated router for the Troubleshooting mode on the /ai page.
Uses NativeToolAgent for interactive terminal + AI conversations
with tool-calling capabilities.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
import logging

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models import User, LLMProvider

router = APIRouter(
    prefix="/api/troubleshoot",
    tags=["troubleshooting"]
)

logger = logging.getLogger(__name__)


@router.post("/chat")
async def troubleshoot_chat(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handle troubleshooting chat messages via REST API.
    
    This endpoint uses the NativeToolAgent for troubleshooting conversations
    with tool calling capabilities (run commands, analyze logs, etc.)
    
    Request body:
        message: str - The user's message
        session_id: str - Session identifier for conversation context
        terminal_context: Optional[str] - Current terminal output for context
    
    Response:
        response: str - AI response with potential [CMD_CARD] markers
        session_id: str - Session ID
        tool_calls: List[str] - Tools that were called during this turn
    """
    from app.services.agentic.native_agent import NativeToolAgent
    
    message = request.get("message", "")
    session_id = request.get("session_id", "")
    terminal_context = request.get("terminal_context", "")
    
    logger.info(f"Troubleshoot chat from {current_user.username}: {message[:100]}...")
    
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
                "session_id": session_id,
                "mode": "troubleshoot"
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
        logger.info(f"Troubleshoot chat response length: {len(full_response)}")
        if "[CMD_CARD]" in full_response:
            logger.info("✅ CMD_CARD markers found in response")
        else:
            logger.debug("No CMD_CARD markers in response (may be expected)")
        
        return {
            "response": full_response,
            "message": full_response,
            "session_id": session_id,
            "tool_calls": tool_calls,
            "mode": "troubleshoot"
        }
        
    except Exception as e:
        logger.error(f"Troubleshoot chat failed: {e}", exc_info=True)
        return {
            "response": f"I apologize, but I encountered an error: {str(e)}",
            "message": f"I apologize, but I encountered an error: {str(e)}",
            "session_id": session_id,
            "mode": "troubleshoot"
        }


@router.get("/sessions")
async def list_troubleshoot_sessions(
    current_user: User = Depends(get_current_user)
):
    """
    List troubleshooting sessions for the current user.
    Returns empty list for now - sessions are handled client-side.
    """
    # TODO: Implement persistent session storage
    return {"sessions": [], "count": 0}


@router.post("/sessions")
async def create_troubleshoot_session(
    current_user: User = Depends(get_current_user)
):
    """
    Create a new troubleshooting session.
    """
    from uuid import uuid4
    from datetime import datetime
    
    session_id = str(uuid4())
    return {
        "id": session_id,
        "user_id": str(current_user.id),
        "created_at": datetime.utcnow().isoformat(),
        "mode": "troubleshoot"
    }
