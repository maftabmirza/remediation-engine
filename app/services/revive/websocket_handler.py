"""
RE-VIVE WebSocket Handler

Provides real-time bidirectional WebSocket communication for the RE-VIVE UI.
Streams AI responses and handles user interjections during the conversation.
"""
import asyncio
import logging
import json
from typing import Dict, Set, Optional
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from sqlalchemy.orm import Session

from app.models import User, LLMProvider
from app.models_ai import AISession, AIMessage
from app.services.revive.orchestrator import ReviveOrchestrator
from app.services.mcp.client import MCPClient
from app.services.ai_permission_service import AIPermissionService
from app.services.pii_mapping_manager import PIIMappingManager

logger = logging.getLogger(__name__)

# Track active WebSocket connections per session
active_connections: Dict[UUID, Set[WebSocket]] = {}

# Connection metadata for better management
connection_metadata: Dict[UUID, Dict[str, any]] = {}


async def broadcast_to_session(session_id: UUID, message: dict):
    """Broadcast a message to all WebSocket connections for a session"""
    if session_id in active_connections:
        dead_connections = set()
        for ws in active_connections[session_id]:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(message)
                else:
                    dead_connections.add(ws)
            except Exception as e:
                logger.debug(f"Failed to broadcast: {e}")
                dead_connections.add(ws)
        # Clean up dead connections
        for ws in dead_connections:
            active_connections[session_id].discard(ws)
            
        # Update connection metadata
        if session_id in connection_metadata:
            connection_metadata[session_id]['last_broadcast'] = asyncio.get_event_loop().time()


async def handle_revive_websocket(
    websocket: WebSocket,
    session_id: str,
    user: User,
    db: Session,
    current_page: Optional[str] = None
):
    """
    Handle WebSocket connection for RE-VIVE chat.
    
    Message Types (Incoming):
    - {"type": "message", "content": "user message", "current_page": "/grafana/..."}
    - {"type": "stop"} - Stop current generation
    
    Message Types (Outgoing):
    - {"type": "connected", "session_id": "..."}
    - {"type": "mode", "mode": "grafana|aiops|auto"}
    - {"type": "chunk", "content": "..."}
    - {"type": "tool_call", "tool_name": "...", "arguments": {...}}
    - {"type": "done", "tool_calls": [...]}
    - {"type": "error", "message": "..."}
    """
    await websocket.accept()
    logger.info(f"RE-VIVE WebSocket connected: session={session_id}, user={user.username}")
    
    # Parse session_id
    try:
        session_uuid = UUID(session_id) if session_id != "new" else None
    except ValueError:
        session_uuid = None
    
    # Load or create session
    ai_session = None
    initial_messages = []
    
    if session_uuid:
        ai_session = db.query(AISession).filter(AISession.id == session_uuid).first()
    
    if not ai_session:
        ai_session = AISession(user_id=user.id, title="RE-VIVE Session")
        db.add(ai_session)
        db.commit()
        db.refresh(ai_session)
        session_uuid = ai_session.id
    else:
        # Load conversation history
        existing_messages = db.query(AIMessage).filter(
            AIMessage.session_id == ai_session.id
        ).order_by(AIMessage.created_at).all()
        
        for msg in existing_messages:
            initial_messages.append({"role": msg.role, "content": msg.content})
    
    # Register connection with metadata
    if session_uuid not in active_connections:
        active_connections[session_uuid] = set()
    active_connections[session_uuid].add(websocket)
    
    # Track connection metadata for monitoring
    connection_metadata[session_uuid] = {
        'user_id': user.id,
        'user_name': user.username,
        'connected_at': asyncio.get_event_loop().time(),
        'last_activity': asyncio.get_event_loop().time(),
        'message_count': 0,
        'current_page': current_page
    }
    
    # Send connected message
    await websocket.send_json({
        "type": "connected",
        "session_id": str(session_uuid)
    })
    
    # Cancellation flag for streaming
    stop_requested = False
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            
            try:
                msg = json.loads(data)
                msg_type = msg.get("type")
                
                if msg_type == "stop":
                    stop_requested = True
                    continue
                
                # Handle heartbeat/ping messages
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": asyncio.get_event_loop().time()})
                    if session_uuid in connection_metadata:
                        connection_metadata[session_uuid]['last_activity'] = asyncio.get_event_loop().time()
                    continue
                
                if msg_type != "message":
                    continue
                
                user_message = msg.get("content", "")
                current_page = msg.get("current_page", current_page)
                explicit_mode = msg.get("mode")
                
                if not user_message:
                    continue
                
                # Reset stop flag
                stop_requested = False
                
                # PII Detection - Load existing mapping from session for consistency
                pii_manager = PIIMappingManager(ai_session.pii_mapping_json or {})
                logger.info(f"🔍 PII MANAGER [RE-VIVE WS]: loaded with {len(pii_manager)} existing mappings")
                
                message_to_use = user_message
                pii_mapping = {}
                pii_service = None
                
                try:
                    from app.services import llm_service

                    pii_factory = getattr(llm_service, "_pii_service_factory", None)
                    logger.info(f"🔍 PII CHECK [RE-VIVE WS]: pii_factory={pii_factory is not None}, message_len={len(user_message)}")
                    
                    if pii_factory and user_message:
                        pii_service = await pii_factory()
                        detection_response = await pii_service.detect(
                            text=user_message,
                            source_type="user_input",
                        )
                        
                        detections = getattr(detection_response, "detections", None) or []
                        logger.info(f"🔍 PII DETECTIONS [RE-VIVE WS]: found {len(detections)} items")

                        if detections:
                            logger.warning(
                                f"Detected {len(detections)} PII/secret(s) in RE-VIVE WS user input"
                            )
                            
                            for detection in detections:
                                await pii_service.log_detection(
                                    detection=detection.model_dump(),
                                    source_type="user_input",
                                    source_id=None,
                                )

                            detection_dicts = [d.model_dump() for d in detections]
                            message_to_use, _ = pii_manager.redact_text_with_mappings(
                                text=user_message,
                                detections=detection_dicts
                            )
                            
                            pii_mapping = pii_manager.get_all_mappings()
                            
                            # Save updated mapping to session
                            ai_session.pii_mapping_json = pii_manager.to_dict()
                            db.commit()
                            
                            logger.info(f"🔍 PII REDACTED [RE-VIVE WS]: total mappings: {len(pii_manager)}")
                except Exception as e:
                    logger.error(f"PII detection failed for RE-VIVE WS: {e}", exc_info=True)
                finally:
                    if pii_service:
                        await pii_service.close()
                
                # Notify frontend if message was redacted
                if message_to_use != user_message:
                    await websocket.send_json({
                        "type": "redacted_input",
                        "pii_mapping": pii_mapping
                    })
                
                # Save user message (potentially redacted)
                user_msg = AIMessage(
                    session_id=session_uuid,
                    role="user",
                    content=message_to_use
                )
                db.add(user_msg)
                db.commit()
                
                # Get LLM provider
                provider = db.query(LLMProvider).filter(
                    LLMProvider.is_default == True,
                    LLMProvider.is_enabled == True
                ).first()
                
                if not provider:
                    provider = db.query(LLMProvider).filter(
                        LLMProvider.is_enabled == True
                    ).first()
                
                if not provider:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No LLM provider configured"
                    })
                    continue
                
                # Setup services
                mcp_client = MCPClient()
                perm_service = AIPermissionService(db)
                
                orchestrator = ReviveOrchestrator(
                    db=db,
                    user=user,
                    mcp_client=mcp_client,
                    permission_service=perm_service,
                    llm_provider=provider,
                    alert_id=None
                )
                
                # Stream response
                full_response = ""
                tool_calls = []
                
                try:
                    async for chunk in orchestrator.run_revive_turn(
                        message_to_use,  # Use potentially redacted message
                        initial_messages,
                        current_page=current_page,
                        explicit_mode=explicit_mode
                    ):
                        if stop_requested:
                            await websocket.send_json({"type": "cancelled"})
                            break
                        
                        # Check if chunk is already formatted or raw
                        if chunk.startswith("data: "):
                            # SSE format from orchestrator, extract JSON
                            try:
                                json_str = chunk[6:]  # Remove "data: " prefix
                                chunk_data = json.loads(json_str.strip())
                                await websocket.send_json(chunk_data)
                                
                                # Accumulate content
                                if chunk_data.get("type") == "chunk":
                                    full_response += chunk_data.get("content", "")
                            except json.JSONDecodeError:
                                pass
                        else:
                            # Raw text chunk
                            full_response += chunk
                            await websocket.send_json({
                                "type": "chunk",
                                "content": chunk
                            })
                        
                        await asyncio.sleep(0.01)
                    
                    # Get tool calls
                    if hasattr(orchestrator, 'tool_calls_made'):
                        tool_calls = orchestrator.tool_calls_made
                    
                    if not stop_requested:
                        # Save assistant response
                        assistant_msg = AIMessage(
                            session_id=session_uuid,
                            role="assistant",
                            content=full_response,
                            metadata_json={"tool_calls": tool_calls} if tool_calls else None
                        )
                        db.add(assistant_msg)
                        db.commit()
                        
                        # Update message history (use redacted version)
                        initial_messages.append({"role": "user", "content": message_to_use})
                        initial_messages.append({"role": "assistant", "content": full_response})
                        
                        # Save updated PII mapping after streaming
                        if pii_manager and len(pii_manager) > 0:
                            ai_session.pii_mapping_json = pii_manager.to_dict()
                            db.commit()
                            logger.info(f"🔍 PII MAPPING FINAL [RE-VIVE WS]: saved {len(pii_manager)} mappings")
                        
                        await websocket.send_json({
                            "type": "done",
                            "tool_calls": tool_calls
                        })
                
                except Exception as e:
                    logger.error(f"Streaming error: {e}", exc_info=True)
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
            
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received from WebSocket")
                continue
    
    except WebSocketDisconnect:
        logger.info(f"RE-VIVE WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Cleanup connection and metadata
        if session_uuid and session_uuid in active_connections:
            active_connections[session_uuid].discard(websocket)
            if not active_connections[session_uuid]:
                del active_connections[session_uuid]
                # Clean up metadata when last connection closes
                if session_uuid in connection_metadata:
                    logger.info(f"Session {session_uuid} disconnected. Total messages: {connection_metadata[session_uuid].get('message_count', 0)}")
                    del connection_metadata[session_uuid]
