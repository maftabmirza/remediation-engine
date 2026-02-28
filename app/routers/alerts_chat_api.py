"""
Alerts Chat API Router

Dedicated to the Alerts Assistant (Chat).
Strictly independent from Troubleshoot and Revive.
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.models import User, LLMProvider, Alert
from app.services.auth_service import get_current_user
from app.models_revive import AISession, AIMessage

router = APIRouter(prefix="/api/alerts/chat", tags=["alerts-chat"])


# Request models
class CreateSessionRequest(BaseModel):
    alert_id: Optional[str] = None


@router.get("/providers")
async def get_chat_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get available LLM providers for alerts chat.
    """
    providers = db.query(LLMProvider).filter(LLMProvider.is_enabled == True).all()
    
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


@router.get("/sessions/by-alert/{alert_id}")
async def get_session_by_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the chat session associated with an alert for the current user.
    """
    try:
        # Check if alert exists
        alert_uuid = UUID(alert_id)
        
        # Searching by context_json for now
        sessions = db.query(AISession).filter(
            AISession.user_id == current_user.id
        ).order_by(AISession.created_at.desc()).limit(20).all()
        
        for session in sessions:
            if session.context_context_json and session.context_context_json.get("alert_id") == alert_id:
                return {
                    "id": str(session.id),
                    "user_id": str(session.user_id),
                    "title": session.title,
                    "created_at": session.created_at.isoformat(),
                    "llm_provider_id": session.context_context_json.get("llm_provider_id")
                }
        
        raise HTTPException(status_code=404, detail="Session not found for this alert")
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert ID")


@router.get("/context-status/{alert_id}")
async def get_context_status(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check status of analysis context for an alert.
    """
    try:
        alert_uuid = UUID(alert_id)
        alert = db.query(Alert).filter(Alert.id == alert_uuid).first()
        
        if not alert:
             raise HTTPException(status_code=404, detail="Alert not found")
             
        return {
            "status": "ready",
            "analyzed": alert.analyzed,
            "analysis_available": bool(alert.ai_analysis),
            # Add simple helpers for badge calculation if needed
            "has_similar_incidents": False, # Placeholder
            "similar_count": 0,
            "has_feedback_history": False,
            "has_correlation": False
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert ID")


@router.post("/sessions")
async def create_chat_session(
    request: Optional[CreateSessionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new alerts chat session.
    """
    session_id = uuid4()
    
    context_type = None
    context_id = None
    context_json = None
    
    if request and request.alert_id:
        try:
            alert_uuid = UUID(request.alert_id)
            context_type = 'alert'
            context_id = alert_uuid
            context_json = {"alert_id": request.alert_id}
        except ValueError:
            pass
            
    new_session = AISession(
        id=session_id,
        user_id=current_user.id,
        pillar="alerts", # Explicit pillar
        title="Alert Chat",
        created_at=datetime.utcnow(),
        context_type=context_type,
        context_id=context_id,
        context_context_json=context_json
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return {
        "id": str(session_id),
        "user_id": str(current_user.id),
        "created_at": new_session.created_at.isoformat()
    }


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get messages for a chat session.
    """
    try:
        session_uuid = UUID(session_id)
        session = db.query(AISession).filter(
            AISession.id == session_uuid,
            AISession.user_id == current_user.id
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
                "created_at": m.created_at.isoformat(),
                "metadata": m.metadata_json
            }
            for m in messages
        ]
    except ValueError:
        return []


@router.patch("/sessions/{session_id}/provider")
async def switch_session_provider(
    session_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Switch the LLM provider for a chat session.
    """
    try:
        provider_id = payload.get("provider_id")
        if not provider_id:
             raise HTTPException(status_code=400, detail="provider_id is required")

        try:
            provider_uuid = UUID(str(provider_id))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid provider ID")

        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_uuid).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        session_uuid = UUID(session_id)
        session = db.query(AISession).filter(
            AISession.id == session_uuid,
            AISession.user_id == current_user.id
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
         raise HTTPException(status_code=400, detail="Invalid session ID")

@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
