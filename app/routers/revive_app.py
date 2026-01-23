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
    
    try:
        # Get LLM Provider
        provider = db.query(LLMProvider).filter(LLMProvider.is_default == True, LLMProvider.is_enabled == True).first()
        if not provider:
            provider = db.query(LLMProvider).filter(LLMProvider.is_enabled == True).first()
        
        if not provider:
            raise HTTPException(status_code=503, detail="No LLM provider configured")
        
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
        
        # Stream response
        async for chunk in orchestrator.run_revive_turn(
            message=request.query,
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
