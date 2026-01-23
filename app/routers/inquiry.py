from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging
import json
import asyncio

from app.database import get_db
from app.models import User, LLMProvider
from app.models_revive import AISession, AIMessage
from app.services.auth_service import get_current_user
from app.services.agentic.inquiry_orchestrator import InquiryOrchestrator
from app.llm_core.provider_selection import get_available_providers

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/inquiry",
    tags=["inquiry"],
    responses={404: {"description": "Not found"}},
)

# --- Request/Response Models ---

class InquiryRequest(BaseModel):
    query: str
    session_id: Optional[UUID] = None
    context: Optional[Dict[str, Any]] = None

class InquiryAPIResponse(BaseModel):
    session_id: UUID
    answer: str
    tools_used: List[str]
    error: Optional[str] = None

# --- Endpoints ---

@router.get("/providers")
async def get_inquiry_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get available LLM providers for inquiry Pillar."""
    providers = get_available_providers(db)
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "provider_name": f"{p.name} ({p.provider_type})",
            "provider_type": p.provider_type,
            "model_id": p.model_id,
            "is_default": p.is_default,
            "is_enabled": p.is_enabled
        }
        for p in providers
    ]

@router.get("/sessions")
async def list_inquiry_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List inquiry chat sessions for the current user."""
    sessions = db.query(AISession).filter(
        AISession.user_id == current_user.id,
        AISession.pillar == "inquiry"
    ).order_by(AISession.created_at.desc()).all()
    
    return {
        "sessions": [
            {
                "id": str(s.id),
                "title": s.title or "Untitled Inquiry",
                "created_at": s.created_at.isoformat(),
                "message_count": len(s.messages)
            }
            for s in sessions
        ],
        "count": len(sessions)
    }

@router.post("/sessions")
async def create_inquiry_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new inquiry session."""
    session_id = uuid4()
    new_session = AISession(
        id=session_id,
        user_id=current_user.id,
        pillar="inquiry",
        title="New Inquiry",
        created_at=datetime.utcnow()
    )
    db.add(new_session)
    db.commit()
    return {
        "id": str(session_id),
        "user_id": str(current_user.id),
        "created_at": new_session.created_at.isoformat()
    }

@router.patch("/sessions/{session_id}/provider")
async def switch_inquiry_provider(
    session_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Switch the LLM provider for an inquiry session."""
    try:
        provider_id = payload.get("provider_id")
        if not provider_id:
             raise HTTPException(status_code=400, detail="provider_id is required")

        provider_uuid = UUID(str(provider_id))
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_uuid).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        session_uuid = UUID(session_id)
        session = db.query(AISession).filter(
            AISession.id == session_uuid,
            AISession.user_id == current_user.id,
            AISession.pillar == "inquiry"
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        ctx = dict(session.context_context_json) if session.context_context_json else {}
        ctx["llm_provider_id"] = str(provider_uuid)
        session.context_context_json = ctx
        db.commit()

        return {
            "success": True,
            "session_id": session_id,
            "provider_name": provider.name,
            "model_name": provider.model_id,
        }
    except ValueError:
         raise HTTPException(status_code=400, detail="Invalid ID format")

@router.get("/sessions/{session_id}/messages")
async def get_inquiry_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get messages for an inquiry session."""
    try:
        session_uuid = UUID(session_id)
        session = db.query(AISession).filter(
            AISession.id == session_uuid,
            AISession.user_id == current_user.id,
            AISession.pillar == "inquiry"
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        messages = db.query(AIMessage).filter(
            AIMessage.session_id == session_uuid
        ).order_by(AIMessage.created_at).all()
        
        return [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

@router.post("/query", response_model=InquiryAPIResponse)
async def query_inquiry(
    request: InquiryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a natural language query to the Inquiry agent."""
    orchestrator = InquiryOrchestrator(db=db, user=current_user)
    result = await orchestrator.process_query(
        query=request.query,
        session_id=request.session_id,
        context=request.context
    )
    
    if result.error == "AccessDenied":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=result.answer)
        
    return InquiryAPIResponse(
        session_id=result.session_id,
        answer=result.answer,
        tools_used=result.tools_used,
        error=result.error
    )

@router.post("/stream")
async def stream_inquiry(
    request: InquiryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stream the inquiry response using SSE."""
    session_id = request.session_id
    
    async def event_generator():
        nonlocal session_id
        full_response = ""
        try:
            # 1. Resolve Session
            ai_session = None
            if session_id:
                ai_session = db.query(AISession).filter(
                    AISession.id == session_id,
                    AISession.user_id == current_user.id,
                    AISession.pillar == "inquiry"
                ).first()
            
            if not ai_session:
                ai_session = AISession(
                    user_id=current_user.id,
                    pillar="inquiry",
                    title=request.query[:100]
                )
                db.add(ai_session)
                db.commit()
                db.refresh(ai_session)
                session_id = ai_session.id
            
            yield f"data: {json.dumps({'type': 'session', 'session_id': str(session_id)})}\n\n"

            # 2. Save User Message
            user_msg = AIMessage(
                session_id=session_id,
                role="user",
                content=request.query
            )
            db.add(user_msg)
            db.commit()

            # 3. Stream from Orchestrator
            provider = None
            if ai_session and ai_session.context_context_json:
                provider_id = ai_session.context_context_json.get("llm_provider_id")
                if provider_id:
                     try:
                         provider = db.query(LLMProvider).filter(LLMProvider.id == UUID(provider_id)).first()
                     except ValueError:
                         pass
            
            orchestrator = InquiryOrchestrator(db=db, user=current_user, provider=provider)
            async for chunk in orchestrator.stream_query(
                query=request.query,
                session_id=session_id,
                context=request.context
            ):
                # If chunk is already data: ... then pass it through
                if chunk.startswith("data: "):
                    yield chunk
                    # Try to extract content if it's a chunk
                    try:
                        data = json.loads(chunk[6:].strip())
                        if data.get('type') == 'chunk':
                            full_response += data.get('content', '')
                    except: pass
                else:
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                
                await asyncio.sleep(0.01)

            # 4. Save Assistant Response
            tool_calls = getattr(orchestrator, 'tool_calls_made', [])
            assistant_msg = AIMessage(
                session_id=session_id,
                role="assistant",
                content=full_response,
                metadata_json={"tool_calls": tool_calls} if tool_calls else None
            )
            db.add(assistant_msg)
            db.commit()

            yield f"data: {json.dumps({'type': 'done', 'tool_calls': tool_calls})}\n\n"

        except Exception as e:
            logger.error(f"Inquiry Streaming error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error: {str(e)}'})}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/event-stream")
