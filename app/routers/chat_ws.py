"""
WebSocket endpoints for Chat
"""
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, LLMProvider
from app.models_chat import ChatSession
from app.services.auth_service import get_current_user_ws
from app.services.chat_service import stream_chat_response

router = APIRouter(tags=["Chat"])

@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: UUID,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time chat.
    """
    # Authenticate
    user = await get_current_user_ws(token, db)
    if not user:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    
    # Verify session ownership
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id
    ).first()
    
    if not session:
        await websocket.close(code=4004)
        return
        
    # Get Provider
    provider = session.llm_provider
    if not provider:
        # Fallback to default
        provider = db.query(LLMProvider).filter(LLMProvider.is_default == True).first()
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            
            # Stream response
            async for chunk in stream_chat_response(db, session_id, data, provider):
                await websocket.send_text(chunk)
                
            # Send end-of-stream marker
            await websocket.send_text("[DONE]")
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_text(f"Error: {str(e)}")
        await websocket.close()
