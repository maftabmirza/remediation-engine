"""
Agent Chat Router
API endpoints for the AI Helper Agent widget.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.services.auth_service import get_current_user
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/agent", tags=["agent"])

class AgentChatRequest(BaseModel):
    message: str
    context: Dict[str, Any]

class AgentChatResponse(BaseModel):
    response: str
    citations: List[str]

@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    request: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Chat with the AI Helper Agent.
    Requires context (URL, title, content) for RAG.
    """
    service = AgentService(db)
    
    try:
        if request.context and "page_content" in request.context:
            content_len = len(request.context["page_content"])
            print(f"DEBUG: Agent received content length: {content_len}")
            print(f"DEBUG: Agent content tail (last 1000 chars):\n{request.context['page_content'][-1000:]}")
        else:
            print("DEBUG: Agent received NO page_content in context")

        result = await service.chat(
            message=request.message,
            context=request.context,
            user=current_user
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
