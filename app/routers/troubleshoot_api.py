"""
Troubleshooting API Router

Dedicated router for the Troubleshooting mode on the /ai page.
Uses NativeToolAgent for interactive terminal + AI conversations
with tool-calling capabilities.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, AsyncGenerator
import logging
import uuid
import json
import os
import asyncio
from pydantic import BaseModel

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models import User, LLMProvider
from app.models_agent import AgentSession, AgentStep
from app.models_revive import AISession, AIMessage
from app.services.pii_mapping_manager import PIIMappingManager

router = APIRouter(
    prefix="/api/troubleshoot",
    tags=["troubleshooting"]
)

class SwitchProviderRequest(dict):
    provider_id: str

class CommandValidateRequest(BaseModel):
    command: str
    server: str

logger = logging.getLogger(__name__)


@router.post("/chat")
async def troubleshoot_chat(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handle troubleshooting chat messages via REST API.
    
    This endpoint uses the TroubleshootNativeAgent for troubleshooting conversations
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
    from app.services.agentic.troubleshoot_native_agent import TroubleshootNativeAgent
    
    message = request.get("message", "")
    session_id = request.get("session_id", "")
    terminal_context = request.get("terminal_context", "")
    
    logger.info(f"Troubleshoot chat from {current_user.username}: {message[:100]}...")
    
    try:
        # === SESSION PERSISTENCE: Load or create session FIRST ===
        ai_session = None
        initial_messages = []
        
        if session_id:
            try:
                session_uuid = uuid.UUID(session_id)
                ai_session = db.query(AISession).filter(AISession.id == session_uuid).first()
            except (ValueError, TypeError):
                logger.warning(f"Invalid session_id format: {session_id}")
        
        if not ai_session:
            # Create new session
            ai_session = AISession(
                user_id=current_user.id,
                pillar="troubleshooting",
                title=message[:100] if message else "Troubleshooting Session"
            )
            db.add(ai_session)
            db.commit()
            db.refresh(ai_session)
            session_id = str(ai_session.id)
            logger.info(f"Created new AI session: {session_id}")
        else:
            # Load existing messages for this session
            existing_messages = db.query(AIMessage).filter(
                AIMessage.session_id == ai_session.id
            ).order_by(AIMessage.created_at).all()
            
            for msg in existing_messages:
                initial_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            logger.info(f"Loaded {len(initial_messages)} messages from session {session_id}")
        
        # === Get LLM Provider - check session's stored provider first ===
        provider = None
        session_ctx = ai_session.context_context_json or {}
        stored_provider_id = session_ctx.get("llm_provider_id")
        
        if stored_provider_id:
            try:
                provider_uuid = uuid.UUID(str(stored_provider_id))
                provider = db.query(LLMProvider).filter(
                    LLMProvider.id == provider_uuid,
                    LLMProvider.is_enabled == True
                ).first()
                if provider:
                    logger.info(f"Using session's stored provider: {provider.name} (type={provider.provider_type}, model={provider.model_id})")
                else:
                    logger.warning(f"Stored provider_id {stored_provider_id} not found or not enabled")
            except (ValueError, TypeError):
                logger.warning(f"Invalid stored provider_id: {stored_provider_id}")
        
        # Fallback to default provider if no session provider
        if not provider:
            provider = db.query(LLMProvider).filter(
                LLMProvider.is_default == True,
                LLMProvider.is_enabled == True
            ).first()
            if provider:
                logger.info(f"Using default provider: {provider.name} (type={provider.provider_type}, model={provider.model_id})")
        
        if not provider:
            provider = db.query(LLMProvider).filter(
                LLMProvider.is_enabled == True
            ).first()
            if provider:
                logger.info(f"Using first enabled provider: {provider.name} (type={provider.provider_type}, model={provider.model_id})")
        
        if not provider:
            return {
                "response": "No LLM provider is configured. Please configure an LLM provider in Settings.",
                "message": "No LLM provider is configured. Please configure an LLM provider in Settings.",
                "session_id": session_id,
                "mode": "troubleshoot"
            }

        # Scan + redact user input for PII/secrets BEFORE persisting and before sending to agent
        # Use session-persistent PIIMappingManager for consistent indexed placeholders
        pii_manager = PIIMappingManager(ai_session.pii_mapping_json or {})
        pii_mapping = {}
        pii_service = None
        pii_detections_for_ui = []  # For frontend highlighting
        original_message = message  # Store original for UI comparison
        
        try:
            from app.services import llm_service

            if getattr(llm_service, "_pii_service_factory", None) and message:
                pii_service = await llm_service._pii_service_factory()
                detection_response = await pii_service.detect(
                    text=message,
                    source_type="user_input",
                )

                detections = getattr(detection_response, "detections", None) or []
                if detections:
                    logger.warning(
                        f"Detected {len(detections)} "
                        "PII/secret(s) in troubleshoot user input - redacting with indexed placeholders"
                    )
                    
                    # Log detections (without UUID source_id - just use source_type for tracking)
                    for detection in detections:
                        await pii_service.log_detection(
                            detection=detection.model_dump(),
                            source_type="user_input",
                            source_id=None,  # Don't pass invalid UUID
                        )

                    # Use PIIMappingManager for consistent indexed redaction
                    detection_dicts = [d.model_dump() for d in detections]
                    message, placeholders_used = pii_manager.redact_text_with_mappings(
                        text=message,
                        detections=detection_dicts
                    )
                    
                    # Get mapping and save to session
                    pii_mapping = pii_manager.get_all_mappings()
                    ai_session.pii_mapping_json = pii_manager.to_dict()
                    db.commit()
                    
                    # Build detection info for UI highlighting
                    for detection, placeholder in zip(detections, placeholders_used):
                        pii_detections_for_ui.append({
                            "original_text": detection.value,
                            "placeholder": placeholder.placeholder,  # Extract placeholder string from PIIPlaceholder object
                            "entity_type": detection.entity_type,
                            "confidence": detection.confidence,
                            "start": detection.start,
                            "end": detection.end,
                            "detection_engine": detection.engine
                        })
                    
                    logger.info(f"🔍 PII REDACTED: '{message[:100]}' | total mappings: {len(pii_manager)}")
        except Exception as e:
            logger.error(f"PII detection failed for troubleshoot user input: {e}", exc_info=True)
            # Continue with original message if PII detection fails
        finally:
            # Close PII service session to prevent connection leaks
            if pii_service:
                await pii_service.close()
        
        # Save the user message to DB
        user_msg = AIMessage(
            session_id=ai_session.id,
            role="user",
            content=message
        )
        db.add(user_msg)
        db.commit()
        
        from app.services.agentic.tools.registry import create_troubleshooting_registry
        
        # Create the Troubleshoot Agent with conversation history
        # Pass PIIMappingManager for consistent PII redaction in tool outputs
        agent = TroubleshootNativeAgent(
            db=db,
            provider=provider,
            alert=None,  # No specific alert context
            initial_messages=initial_messages,
            registry_factory=create_troubleshooting_registry,
            pii_mapping_manager=pii_manager
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
        
        # Save the assistant response to DB
        assistant_msg = AIMessage(
            session_id=ai_session.id,
            role="assistant",
            content=full_response,
            metadata_json={"tool_calls": tool_calls} if tool_calls else None
        )
        db.add(assistant_msg)
        db.commit()
        
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
            "mode": "troubleshoot",
            "pii_detections": pii_detections_for_ui,  # For UI highlighting
            "pii_mapping": pii_mapping  # For de-anonymization
        }
        
    except Exception as e:
        logger.error(f"Troubleshoot chat failed: {e}", exc_info=True)
        return {
            "response": f"I apologize, but I encountered an error: {str(e)}",
            "message": f"I apologize, but I encountered an error: {str(e)}",
            "session_id": session_id,
            "mode": "troubleshoot"
        }


@router.post("/chat/stream")
async def troubleshoot_chat_stream(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Streaming endpoint for troubleshooting chat using Server-Sent Events (SSE).
    
    Returns real-time token-by-token responses for better UX.
    Each SSE event is a JSON object with type and content.
    """
    from app.services.agentic.troubleshoot_native_agent import TroubleshootNativeAgent
    from app.services.agentic.tools.registry import create_troubleshooting_registry
    
    message = request.get("message", "")
    session_id = request.get("session_id", "")
    
    logger.info(f"Troubleshoot stream from {current_user.username}: {message[:100]}...")
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        nonlocal session_id
        full_response = ""
        tool_calls = []
        
        logger.info(f"🚀 STREAM GENERATOR STARTED for message: '{message[:50]}...'")
        
        try:
            # === SESSION PERSISTENCE - Load or create session FIRST ===
            ai_session = None
            initial_messages = []
            
            if session_id:
                try:
                    session_uuid = uuid.UUID(session_id)
                    ai_session = db.query(AISession).filter(AISession.id == session_uuid).first()
                except (ValueError, TypeError):
                    pass
            
            if not ai_session:
                ai_session = AISession(
                    user_id=current_user.id,
                    pillar="troubleshooting",
                    title=message[:100] if message else "Troubleshooting Session"
                )
                db.add(ai_session)
                db.commit()
                db.refresh(ai_session)
                session_id = str(ai_session.id)
            else:
                existing_messages = db.query(AIMessage).filter(
                    AIMessage.session_id == ai_session.id
                ).order_by(AIMessage.created_at).all()
                
                for msg in existing_messages:
                    initial_messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # === Get LLM Provider - check session's stored provider first ===
            provider = None
            session_ctx = ai_session.context_context_json or {}
            stored_provider_id = session_ctx.get("llm_provider_id")
            
            if stored_provider_id:
                try:
                    provider_uuid = uuid.UUID(str(stored_provider_id))
                    provider = db.query(LLMProvider).filter(
                        LLMProvider.id == provider_uuid,
                        LLMProvider.is_enabled == True
                    ).first()
                    if provider:
                        logger.info(f"Streaming: Using session's stored provider: {provider.name} (type={provider.provider_type}, model={provider.model_id})")
                    else:
                        logger.warning(f"Streaming: Stored provider_id {stored_provider_id} not found or not enabled")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid stored provider_id: {stored_provider_id}")
            
            # Fallback to default provider if no session provider
            if not provider:
                provider = db.query(LLMProvider).filter(
                    LLMProvider.is_default == True,
                    LLMProvider.is_enabled == True
                ).first()
                if provider:
                    logger.info(f"Streaming: Using default provider: {provider.name} (type={provider.provider_type}, model={provider.model_id})")
            
            if not provider:
                provider = db.query(LLMProvider).filter(
                    LLMProvider.is_enabled == True
                ).first()
                if provider:
                    logger.info(f"Streaming: Using first enabled provider: {provider.name} (type={provider.provider_type}, model={provider.model_id})")
            
            if not provider:
                yield f"data: {json.dumps({'type': 'error', 'content': 'No LLM provider configured'})}\n\n"
                return

            # Scan + redact user input for PII/secrets BEFORE persisting and before sending to agent
            # Use session-persistent PIIMappingManager for consistent indexed placeholders
            message_to_use = message
            pii_mapping = {}
            pii_service = None
            pii_detections_for_ui = []  # For UI highlighting
            
            # Load existing PII mapping from session for consistency across messages
            pii_manager = PIIMappingManager(ai_session.pii_mapping_json or {})
            logger.info(f"🔍 PII MANAGER: loaded with {len(pii_manager)} existing mappings")
            
            try:
                from app.services import llm_service

                pii_factory = getattr(llm_service, "_pii_service_factory", None)
                logger.info(f"🔍 PII CHECK: pii_factory={pii_factory is not None}, message_len={len(message) if message else 0}")
                
                if pii_factory and message:
                    pii_service = await pii_factory()
                    logger.info(f"🔍 PII SERVICE: created, detecting on '{message[:50]}...'")
                    detection_response = await pii_service.detect(
                        text=message,
                        source_type="user_input",
                    )
                    
                    detections = getattr(detection_response, "detections", None) or []
                    logger.info(f"🔍 PII DETECTIONS: found {len(detections)} items")

                    if detections:
                        logger.warning(
                            f"Detected {len(detections)} "
                            "PII/secret(s) in troubleshoot user input - redacting with indexed placeholders"
                        )
                        
                        # Log detections to database (without UUID source_id)
                        for detection in detections:
                            logger.info(f"🔍 PII ITEM: {detection}")
                            await pii_service.log_detection(
                                detection=detection.model_dump(),
                                source_type="user_input",
                                source_id=None,  # Don't pass invalid UUID
                            )

                        # Use PIIMappingManager for consistent indexed redaction
                        # This ensures same PII value always gets same placeholder across session
                        detection_dicts = [d.model_dump() for d in detections]
                        message_to_use, placeholders_used = pii_manager.redact_text_with_mappings(
                            text=message,
                            detections=detection_dicts
                        )
                        
                        # Get full mapping for frontend (for de-anonymization of AI response)
                        pii_mapping = pii_manager.get_all_mappings()
                        
                        # Save updated mapping back to session
                        ai_session.pii_mapping_json = pii_manager.to_dict()
                        db.commit()
                        
                        # Build detection info for UI highlighting
                        for detection, placeholder in zip(detections, placeholders_used):
                            pii_detections_for_ui.append({
                                "original_text": detection.value,
                                "placeholder": placeholder.placeholder,  # Extract placeholder string from PIIPlaceholder object
                                "entity_type": detection.entity_type,
                                "confidence": detection.confidence,
                                "start": detection.start,
                                "end": detection.end,
                                "detection_engine": detection.engine
                            })
                        
                        logger.info(f"🔍 PII REDACTED: '{message_to_use[:100]}' | total mappings: {len(pii_manager)}")
                        logger.info(f"🔍 PII MAPPING SAVED to session: {pii_manager.get_stats()}")
                else:
                    logger.warning(f"⚠️ PII SKIPPED: factory={pii_factory is not None}, message={bool(message)}")
            except Exception as e:
                logger.error(f"PII detection failed for troubleshoot user input: {e}", exc_info=True)
                message_to_use = message
                pii_mapping = {}
            finally:
                # Close PII service session to prevent connection leaks
                if pii_service:
                    await pii_service.close()
            
            # Send session_id first
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
            
            # If message was redacted, notify frontend with detection details for highlighting
            if pii_detections_for_ui:
                yield f"data: {json.dumps({'type': 'pii_detections', 'detections': pii_detections_for_ui})}\n\n"
                yield f"data: {json.dumps({'type': 'redacted_input', 'pii_mapping': pii_mapping})}\n\n"
            
            # Save user message
            user_msg = AIMessage(
                session_id=ai_session.id,
                role="user",
                content=message_to_use
            )
            db.add(user_msg)
            db.commit()
            
            # Create agent with history and troubleshooting-specific tools
            # Pass PIIMappingManager for consistent PII redaction in tool outputs
            agent = TroubleshootNativeAgent(
                db=db,
                provider=provider,
                alert=None,
                initial_messages=initial_messages,
                registry_factory=create_troubleshooting_registry,
                pii_mapping_manager=pii_manager
            )
            
            # Stream chunks to client
            async for chunk in agent.stream(message_to_use):
                full_response += chunk
                # Send each chunk as SSE event
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                # Small delay to prevent overwhelming the client
                await asyncio.sleep(0.01)
            
            # Save updated PII mapping after streaming (may have new mappings from tool outputs)
            if pii_manager and len(pii_manager) > 0:
                ai_session.pii_mapping_json = pii_manager.to_dict()
                db.commit()
                logger.info(f"🔍 PII MAPPING FINAL: saved {len(pii_manager)} mappings to session")
            
            # Get tool calls
            if hasattr(agent, 'tool_calls_made'):
                tool_calls = agent.tool_calls_made
            
            # Save Assistant Response
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
            logger.info("Stream cancelled by client")
            yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
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
async def list_troubleshoot_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List troubleshooting sessions for the current user.
    """
    sessions = db.query(AISession).filter(
        AISession.user_id == current_user.id,
        AISession.pillar == "troubleshooting",
    ).order_by(AISession.created_at.desc()).all()
    
    return {
        "sessions": [
            {
                "id": str(s.id),
                "title": s.title or "Untitled Session",
                "created_at": s.created_at.isoformat(),
                "updated_at": s.created_at.isoformat()
            }
            for s in sessions
        ],
        "count": len(sessions)
    }


@router.get("/providers")
async def list_troubleshoot_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List available LLM providers for troubleshooting."""
    from app.llm_core.provider_selection import get_available_providers
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

@router.post("/sessions")
async def create_troubleshoot_session(
    request: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new troubleshooting session."""
    session = AISession(
        user_id=current_user.id,
        pillar="troubleshooting",
        context_type="standalone",
        title="Troubleshooting Session"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info(f"Created new session {session.id} for user {current_user.username}")
    
    return {
        "id": str(session.id),
        "title": session.title,
        "llm_provider_id": None
    }


@router.get("/sessions/standalone")
async def get_standalone_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the current standalone troubleshooting session or create one."""
    session = db.query(AISession).filter(
        AISession.user_id == current_user.id,
        AISession.pillar == "troubleshooting",
        AISession.context_type == "standalone"
    ).order_by(AISession.created_at.desc()).first()

    if not session:
        session = AISession(
            user_id=current_user.id,
            pillar="troubleshooting",
            context_type="standalone",
            title="Troubleshooting Session"
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # Get provider ID from context if set
    llm_provider_id = None
    if session.context_context_json:
        llm_provider_id = session.context_context_json.get("llm_provider_id")

    return {
        "id": str(session.id),
        "title": session.title,
        "llm_provider_id": llm_provider_id
    }

@router.get("/sessions/{session_id}/messages")
async def get_troubleshoot_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get messages for a troubleshooting session with PII de-anonymization mapping."""
    try:
        session_uuid = uuid.UUID(session_id)
        session = db.query(AISession).filter(
            AISession.id == session_uuid,
            AISession.user_id == current_user.id,
            AISession.pillar == "troubleshooting",
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Load PII mapping for de-anonymization (placeholder → original)
        pii_mapping = {}
        if session.pii_mapping_json:
            # Extract only the forward mappings (placeholder → original), not metadata
            for key, value in session.pii_mapping_json.items():
                if not key.startswith("_"):  # Skip _counters, _reverse
                    pii_mapping[key] = value
            logger.info(f"get_troubleshoot_messages: loaded {len(pii_mapping)} PII mappings for de-anonymization")

        messages = db.query(AIMessage).filter(
            AIMessage.session_id == session_uuid
        ).order_by(AIMessage.created_at).all()

        logger.info(f"get_troubleshoot_messages: session={session_id}, found {len(messages)} persisted messages")

        # Agent-linked sessions can exist with partial/empty persisted chat history.
        # If linked, we ensure the UI sees at least the goal and any agent steps.
        agent = db.query(AgentSession).filter(
            AgentSession.user_id == current_user.id,
            AgentSession.chat_session_id == session_uuid,
        ).order_by(AgentSession.created_at.desc()).first()

        if agent:
            logger.info(f"  -> agent-linked session: agent_id={agent.id}, goal={agent.goal[:50] if agent.goal else 'None'}")
            goal_text = agent.goal or (session.title or "Agent Session")
            has_user = any(m.role == "user" for m in messages)
            has_any = len(messages) > 0

            # If there are no persisted chat messages at all, return a synthetic history.
            if not has_any:
                synthetic = [
                    {
                        "id": f"agent-{agent.id}-goal",
                        "role": "user",
                        "content": goal_text,
                        "created_at": agent.created_at.isoformat() if agent.created_at else session.created_at.isoformat(),
                        "metadata": {"synthetic": True, "source": "agent_goal", "agent_session_id": str(agent.id)},
                    }
                ]
                steps = db.query(AgentStep).filter(
                    AgentStep.agent_session_id == agent.id
                ).order_by(AgentStep.step_number.asc()).all()

                for st in steps:
                    if st.step_type == "command":
                        content = st.content
                        if st.output:
                            content += "\n\nOutput:\n" + st.output
                        if st.exit_code is not None:
                            content += f"\n\nExit code: {st.exit_code}"
                    else:
                        content = st.content

                    synthetic.append(
                        {
                            "id": f"agent-{agent.id}-step-{st.step_number}",
                            "role": "assistant",
                            "content": content,
                            "created_at": st.created_at.isoformat() if st.created_at else session.created_at.isoformat(),
                            "metadata": {
                                "synthetic": True,
                                "source": "agent_step",
                                "agent_session_id": str(agent.id),
                                "step_number": st.step_number,
                                "step_type": st.step_type,
                                "status": st.status,
                            },
                        }
                    )
                return {"messages": synthetic, "pii_mapping": pii_mapping}

            # If we have messages but no user goal message, prepend a synthetic goal.
            if not has_user:
                prepend = {
                    "id": f"agent-{agent.id}-goal",
                    "role": "user",
                    "content": goal_text,
                    "created_at": agent.created_at.isoformat() if agent.created_at else session.created_at.isoformat(),
                    "metadata": {"synthetic": True, "source": "agent_goal", "agent_session_id": str(agent.id)},
                }
                msgs = [prepend] + [
                    {
                        "id": str(m.id),
                        "role": m.role,
                        "content": m.content,
                        "created_at": m.created_at.isoformat(),
                        "metadata": m.metadata_json,
                    }
                    for m in messages
                ]
                return {"messages": msgs, "pii_mapping": pii_mapping}
        
        result = [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "metadata": m.metadata_json
            }
            for m in messages
        ]
        logger.info(f"  -> returning {len(result)} messages (roles: {[m['role'] for m in result]}), pii_mapping={len(pii_mapping)} entries")
        return {"messages": result, "pii_mapping": pii_mapping}
    except Exception as e:
        logger.error(f"Failed to get messages: {e}")
        raise HTTPException(status_code=400, detail="Invalid session ID")

@router.patch("/sessions/{session_id}/provider")
async def switch_troubleshoot_provider(
    session_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Switch LLM provider for a session."""
    try:
        provider_id = payload.get("provider_id")
        if not provider_id:
            raise HTTPException(status_code=400, detail="provider_id required")

        # Look up the provider to get its name and model_id
        try:
            provider_uuid = uuid.UUID(str(provider_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid provider ID format")
        
        provider = db.query(LLMProvider).filter(LLMProvider.id == provider_uuid).first()
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        session_uuid = uuid.UUID(session_id)
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Switch provider failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/commands/validate")
async def validate_command_troubleshoot(
    request: CommandValidateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Validate a command before execution.
    Returns safety assessment and risk level.
    """
    from app.services.command_validator import CommandValidator
    
    try:
        validator = CommandValidator()
        
        # Detect OS type from server name
        os_type = "windows" if any(x in request.server.lower() for x in ['win', 'windows']) else "linux"
        
        # Validate command
        result = validator.validate_command(request.command, os_type)
        
        return {
            "result": result.result.value,
            "message": result.message,
            "risk_level": result.risk_level if hasattr(result, 'risk_level') else 'unknown'
        }
    except Exception as e:
        return {
            "result": "unknown",
            "message": f"Validation error: {str(e)}",
            "risk_level": "unknown"
        }
