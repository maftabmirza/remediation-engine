"""
RE-VIVE Application Helper Router

Dedicated to the general application helper (non-Grafana/MCP contexts).
Strictly separated from other pillars.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import logging
import json

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models import User, LLMProvider
from app.services.revive.orchestrator import ReviveOrchestrator
from app.services.ai_permission_service import AIPermissionService
from app.schemas_revive import AIHelperQueryRequest, AIHelperQueryResponse
from app.services.pii_mapping_manager import PIIMappingManager

# Unique prefix for this flow
router = APIRouter(
    prefix="/api/revive/app",
    tags=["revive-app"]
)

logger = logging.getLogger(__name__)

@router.post("/query", response_model=AIHelperQueryResponse)
async def revive_app_query(
    request: AIHelperQueryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handle app-context queries (Runbooks, Dashboard explanations, etc).
    No MCP/Grafana access in this flow.
    """
    logger.info(f"RE-VIVE App query from {current_user.username}: {request.query}")
    
    pii_service = None
    
    try:
        # Get LLM Provider
        provider = db.query(LLMProvider).filter(LLMProvider.is_default == True, LLMProvider.is_enabled == True).first()
        if not provider:
            provider = db.query(LLMProvider).filter(LLMProvider.is_enabled == True).first()
        
        if not provider:
            raise HTTPException(status_code=503, detail="No LLM provider configured")
        
        # PII Detection for user query
        query_to_use = request.query
        pii_mapping = {}
        pii_manager = PIIMappingManager({})
        
        try:
            from app.services import llm_service

            pii_factory = getattr(llm_service, "_pii_service_factory", None)
            logger.info(f"🔍 PII CHECK [RE-VIVE APP]: pii_factory={pii_factory is not None}, query_len={len(request.query) if request.query else 0}")
            
            if pii_factory and request.query:
                pii_service = await pii_factory()
                detection_response = await pii_service.detect(
                    text=request.query,
                    source_type="user_input",
                )
                
                detections = getattr(detection_response, "detections", None) or []
                logger.info(f"🔍 PII DETECTIONS [RE-VIVE APP]: found {len(detections)} items")

                if detections:
                    logger.warning(f"Detected {len(detections)} PII/secret(s) in RE-VIVE App query")
                    
                    for detection in detections:
                        await pii_service.log_detection(
                            detection=detection.model_dump(),
                            source_type="user_input",
                            source_id=None,
                        )

                    detection_dicts = [d.model_dump() for d in detections]
                    query_to_use, _ = pii_manager.redact_text_with_mappings(
                        text=request.query,
                        detections=detection_dicts
                    )
                    
                    pii_mapping = pii_manager.get_all_mappings()
                    logger.info(f"🔍 PII REDACTED [RE-VIVE APP]: total mappings: {len(pii_manager)}")
        except Exception as e:
            logger.error(f"PII detection failed for RE-VIVE App: {e}", exc_info=True)
        finally:
            if pii_service:
                await pii_service.close()
                pii_service = None
        
        # Initialize services
        perm_service = AIPermissionService(db)
        
        # Instantiate Orchestrator purely for App flow
        # explicit_mode="app" could be enforced if the orchestrator supports it
        # mcp_client=None enforces no MCP tools
        orchestrator = ReviveOrchestrator(
            db=db,
            user=current_user,
            mcp_client=None,  # STRICT: No MCP for general app helper
            permission_service=perm_service,
            llm_provider=provider,
            alert_id=None
        )
        
        full_response = ""
        intent = "general"
        confidence = 0.0
        sources = []
        
        # Stream response (with potentially redacted query)
        async for chunk in orchestrator.run_revive_turn(
            message=query_to_use,
            session_messages=[], # TODO: Add session state if needed
            page_context=request.page_context,
            explicit_mode="general" # Bias towards general app assistance
        ):
             # Parse streamed chunks (SSE format from orchestrator)
            if chunk.startswith("data: "):
                data_str = chunk[6:].strip()
                if data_str:
                    try:
                        data = json.loads(data_str)
                        chunk_type = data.get('type')
                        
                        if chunk_type == 'mode':
                            intent = data.get('content', 'general')
                        elif chunk_type == 'chunk':
                            content = data.get('content', '')
                            full_response += content
                        elif chunk_type == 'done':
                            sources = data.get('tool_calls', [])
                            confidence = 0.9 if sources else 0.5
                    except json.JSONDecodeError:
                        full_response += chunk
            else:
                full_response += chunk

        return AIHelperQueryResponse(
            response=full_response or "I apologize, but I couldn't generate a response.",
            session_id=request.session_id,
            intent=intent,
            confidence=confidence,
            sources=[{"type": "tool", "name": tool} for tool in sources] if sources else []
        )

    except Exception as e:
        logger.error(f"RE-VIVE App query failed: {e}", exc_info=True)
        return AIHelperQueryResponse(
            response=f"Error processing query: {str(e)}",
            session_id=request.session_id,
            confidence=0.0
        )
