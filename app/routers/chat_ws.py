"""WebSocket endpoints for Chat."""
import logging
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState

from app.database import get_db
from app.models import User, LLMProvider
from app.models_chat import ChatSession
from app.services.auth_service import get_current_user_ws
from app.services.chat_service import stream_chat_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Chat"])

# WebSocket close codes
WS_CLOSE_AUTH_FAILED = 4001
WS_CLOSE_SESSION_NOT_FOUND = 4004
WS_CLOSE_NO_PROVIDER = 4010
WS_CLOSE_INTERNAL_ERROR = 4500


async def safe_send(websocket: WebSocket, message: str) -> bool:
    """Safely send a message to WebSocket, returning False if connection is closed."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(message)
            return True
    except Exception as e:
        logger.debug(f"Failed to send WebSocket message: {e}")
    return False


async def safe_close(websocket: WebSocket, code: int = 1000) -> None:
    """Safely close a WebSocket connection."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=code)
    except Exception as e:
        logger.debug(f"Error closing WebSocket: {e}")


@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: UUID,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time chat.
    
    Close codes:
        - 4001: Authentication failed
        - 4004: Chat session not found or access denied
        - 4010: No LLM provider configured
        - 4500: Internal server error
    """
    # Authenticate
    user = await get_current_user_ws(token, db)
    if not user:
        logger.warning(f"Chat WebSocket auth failed for session {session_id}")
        await websocket.close(code=WS_CLOSE_AUTH_FAILED)
        return

    await websocket.accept()
    logger.info(f"Chat WebSocket connected: user={user.username}, session={session_id}")
    
    # Verify session ownership
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id
    ).first()
    
    if not session:
        logger.warning(f"Chat session not found or access denied: {session_id}")
        await safe_send(websocket, '{"type":"error","message":"Session not found"}')
        await safe_close(websocket, WS_CLOSE_SESSION_NOT_FOUND)
        return
        
    # Get Provider
    provider = session.llm_provider
    if not provider:
        # Fallback to default
        provider = db.query(LLMProvider).filter(
            LLMProvider.is_default == True,
            LLMProvider.is_enabled == True
        ).first()
    
    if not provider:
        logger.error(f"No LLM provider available for chat session {session_id}")
        await safe_send(websocket, '{"type":"error","message":"No LLM provider configured"}')
        await safe_close(websocket, WS_CLOSE_NO_PROVIDER)
        return
    
    try:
        while True:
            # Receive message
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                logger.debug(f"Chat WebSocket disconnected: session={session_id}")
                break
            
            if not data or not data.strip():
                await safe_send(websocket, '{"type":"error","message":"Empty message"}')
                continue
            
            # Stream response
            try:
                async for chunk in stream_chat_response(db, session_id, data, provider):
                    if not await safe_send(websocket, chunk):
                        logger.debug("Client disconnected during streaming")
                        return
                        
                # Send end-of-stream marker
                await safe_send(websocket, "[DONE]")
                
            except Exception as e:
                logger.error(f"Error streaming chat response: {e}", exc_info=True)
                error_msg = '{"type":"error","message":"Failed to generate response"}'
                await safe_send(websocket, error_msg)
                await safe_send(websocket, "[DONE]")
            
    except WebSocketDisconnect:
        logger.info(f"Chat WebSocket disconnected: user={user.username}, session={session_id}")
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}", exc_info=True)
        await safe_send(websocket, f'{{"type":"error","message":"Internal error: {str(e)}"}}')
    finally:
        await safe_close(websocket)
        logger.debug(f"Chat WebSocket closed: session={session_id}")
