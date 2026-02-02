from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, AsyncGenerator
import logging
import uuid
import json
import asyncio
from datetime import datetime

from app.database import get_db
from app.services.auth_service import get_current_user, get_current_user_ws
from app.models import User, LLMProvider
from app.models_ai import AISession, AIMessage
from app.services.pii_mapping_manager import PIIMappingManager

router = APIRouter(
    prefix="/api/revive",
    tags=["revive"]
)
# Separate router for WebSocket (no prefix)
ws_router = APIRouter(tags=["revive-ws"])

logger = logging.getLogger(__name__)

@router.post("/chat/stream")
async def revive_chat_stream(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Streaming chat endpoint for RE-VIVE Unified Assistant.
    """
    from app.services.revive.orchestrator import ReviveOrchestrator
    from app.services.mcp.client import MCPClient
    from app.services.ai_permission_service import AIPermissionService
    
    message = request.get("message", "")
    session_id = request.get("session_id", "")
    current_page = request.get("current_page", "") # For context-aware mode detection
    explicit_mode = request.get("mode", "") # For explicit mode override
    
    logger.info(f"Revive stream from {current_user.username}: {message[:50]}... (Page: {current_page})")
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        nonlocal session_id
        full_response = ""
        tool_calls = []
        message_to_use = message
        pii_mapping = {}
        pii_service = None
        
        try:
            # 1. Get LLM Provider
            provider = db.query(LLMProvider).filter(LLMProvider.is_default == True, LLMProvider.is_enabled == True).first()
            if not provider:
                provider = db.query(LLMProvider).filter(LLMProvider.is_enabled == True).first()
            if not provider:
                yield f"data: {json.dumps({'type': 'error', 'content': 'No LLM provider configured'})}\n\n"
                return

            # 2. Session Management
            ai_session = None
            initial_messages = []
            
            if session_id:
                try:
                    session_uuid = uuid.UUID(session_id)
                    ai_session = db.query(AISession).filter(AISession.id == session_uuid).first()
                except (ValueError, TypeError):
                    pass
            
            if not ai_session:
                ai_session = AISession(user_id=current_user.id, title=message[:100] if message else "RE-VIVE Session")
                db.add(ai_session)
                db.commit()
                db.refresh(ai_session)
                session_id = str(ai_session.id)
            else:
                existing_messages = db.query(AIMessage).filter(AIMessage.session_id == ai_session.id).order_by(AIMessage.created_at).all()
                for msg in existing_messages:
                    initial_messages.append({"role": msg.role, "content": msg.content})
            
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
            
            # 2.5. PII Detection - Load existing PII mapping from session for consistency
            pii_manager = PIIMappingManager(ai_session.pii_mapping_json or {})
            logger.info(f"🔍 PII MANAGER [RE-VIVE]: loaded with {len(pii_manager)} existing mappings")
            
            try:
                from app.services import llm_service

                pii_factory = getattr(llm_service, "_pii_service_factory", None)
                logger.info(f"🔍 PII CHECK [RE-VIVE]: pii_factory={pii_factory is not None}, message_len={len(message) if message else 0}")
                
                if pii_factory and message:
                    pii_service = await pii_factory()
                    logger.info(f"🔍 PII SERVICE [RE-VIVE]: created, detecting on '{message[:50]}...'")
                    detection_response = await pii_service.detect(
                        text=message,
                        source_type="user_input",
                    )
                    
                    detections = getattr(detection_response, "detections", None) or []
                    logger.info(f"🔍 PII DETECTIONS [RE-VIVE]: found {len(detections)} items")

                    if detections:
                        logger.warning(
                            f"Detected {len(detections)} "
                            "PII/secret(s) in RE-VIVE user input - redacting with indexed placeholders"
                        )
                        
                        for detection in detections:
                            await pii_service.log_detection(
                                detection=detection.model_dump(),
                                source_type="user_input",
                                source_id=None,
                            )

                        # Use PIIMappingManager for consistent indexed redaction
                        detection_dicts = [d.model_dump() for d in detections]
                        message_to_use, _ = pii_manager.redact_text_with_mappings(
                            text=message,
                            detections=detection_dicts
                        )
                        
                        pii_mapping = pii_manager.get_all_mappings()
                        
                        # Save updated mapping back to session
                        ai_session.pii_mapping_json = pii_manager.to_dict()
                        db.commit()
                        
                        logger.info(f"🔍 PII REDACTED [RE-VIVE]: '{message_to_use[:100]}' | total mappings: {len(pii_manager)}")
                else:
                    logger.warning(f"⚠️ PII SKIPPED [RE-VIVE]: factory={pii_factory is not None}, message={bool(message)}")
            except Exception as e:
                logger.error(f"PII detection failed for RE-VIVE user input: {e}", exc_info=True)
                message_to_use = message
                pii_mapping = {}
            finally:
                if pii_service:
                    await pii_service.close()
            
            # Notify frontend if message was redacted
            if message_to_use != message:
                yield f"data: {json.dumps({'type': 'redacted_input', 'pii_mapping': pii_mapping})}\n\n"
            
            # 3. Save User Message (potentially redacted)
            user_msg = AIMessage(session_id=ai_session.id, role="user", content=message_to_use)
            db.add(user_msg)
            db.commit()
            
            # 4. Setup Services - Use MCP connection pool
            from app.services.mcp.pool import get_mcp_client
            import os
            
            mcp_client = None
            mcp_grafana_url = os.getenv("MCP_GRAFANA_URL")
            if mcp_grafana_url:
                try:
                    mcp_client = await get_mcp_client(server_url=mcp_grafana_url)
                except Exception as e:
                    logger.warning(f"Failed to get MCP client: {e}. Continuing without MCP support.")
            
            perm_service = AIPermissionService(db)
            
            orchestrator = ReviveOrchestrator(
                db=db,
                user=current_user,
                mcp_client=mcp_client,
                permission_service=perm_service,
                llm_provider=provider,
                alert_id=None # Revive is general purpose, but could support alert context if passed
            )
            
            # 5. Run Orchestrator Loop (with potentially redacted message)
            async for chunk in orchestrator.run_revive_turn(
                message_to_use, 
                initial_messages,
                current_page=current_page,
                explicit_mode=explicit_mode
            ):
                # Try to parse chunk if it's already JSON (from Mode Detector) or raw text (from Agent)
                # If chunk starts with "data: ", yield it directly
                if chunk.startswith("data: "):
                    yield chunk
                else:
                    # It's content from the agent
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                await asyncio.sleep(0.01)
            
            # Save updated PII mapping after streaming (may have new mappings from tool outputs)
            if pii_manager and len(pii_manager) > 0:
                ai_session.pii_mapping_json = pii_manager.to_dict()
                db.commit()
                logger.info(f"🔍 PII MAPPING FINAL [RE-VIVE]: saved {len(pii_manager)} mappings to session")
                
            # 6. Finalize
            if hasattr(orchestrator, 'tool_calls_made'):
                tool_calls = orchestrator.tool_calls_made
                
            assistant_msg = AIMessage(
                session_id=ai_session.id,
                role="assistant",
                content=full_response,
                metadata_json={"tool_calls": tool_calls} if tool_calls else None
            )
            db.add(assistant_msg)
            db.commit()
            
            yield f"data: {json.dumps({'type': 'done', 'tool_calls': tool_calls})}\n\n"
            
        except asyncio.CancelledError:
            logger.info("Revive stream cancelled client")
            yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
        except Exception as e:
            logger.error(f"Revive stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/sessions")
async def list_revive_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sessions = db.query(AISession).filter(
        AISession.user_id == current_user.id
    ).order_by(AISession.updated_at.desc()).limit(20).all()
    
    return {
        "sessions": [
            {
                "id": str(s.id),
                "title": s.title or "Untitled",
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat()
            }
            for s in sessions
        ]
    }


@ws_router.websocket("/ws/revive/{session_id}")
async def revive_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
    current_page: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time RE-VIVE chat.
    
    Query params:
    - token: Authentication token
    - current_page: Optional page context for mode detection
    """
    from app.services.revive.websocket_handler import handle_revive_websocket
    
    # Authenticate
    user = await get_current_user_ws(token, db)
    if not user:
        await websocket.close(code=4001)
        return
    
    await handle_revive_websocket(websocket, session_id, user, db, current_page)
