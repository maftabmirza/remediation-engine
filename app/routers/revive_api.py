"""
AI Helper Widget API 

Full-featured router to support the AI Helper widget.
Routes to the AI Helper Orchestrator for context-aware assistance.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
import logging
import os
import json

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models import User, LLMProvider
from app.services.revive.orchestrator import ReviveOrchestrator
from app.services.mcp.client import MCPClient
from app.services.ai_permission_service import AIPermissionService
from app.schemas_revive import AIHelperQueryRequest, AIHelperQueryResponse

router = APIRouter(
    prefix="/api/ai-helper",
    tags=["ai-helper"]
)

logger = logging.getLogger(__name__)


@router.post("/query", response_model=AIHelperQueryResponse)
async def ai_helper_query(
    request: AIHelperQueryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handle AI Helper widget queries with MCP support.
    
    Routes to the MCP-aware RE-VIVE Orchestrator which automatically detects
    Grafana/Prometheus queries and uses appropriate MCP tools.
    """
    logger.info(f"AI Helper query from {current_user.username}: {request.query}")
    
    # DEBUG: Log incoming page context
    if request.page_context:
        logger.warning(f"🔍 API DEBUG: Page context received from frontend")
        logger.warning(f"  - Page Type: {request.page_context.get('page_type', 'unknown')}")
        logger.warning(f"  - Page Title: {request.page_context.get('title', 'unknown')}")
        logger.warning(f"  - Client Tools Used: {request.page_context.get('client_tools_used', False)}")
        logger.warning(f"  - Has Page Specific Data: {bool(request.page_context.get('page_specific_data'))}")
        if request.page_context.get('page_specific_data'):
            psd = request.page_context['page_specific_data']
            logger.warning(f"  - Runbook ID: {psd.get('runbook_id', 'N/A')}")
            logger.warning(f"  - Steps Count: {len(psd.get('steps', []))}")
    else:
        logger.warning("🔍 API DEBUG: NO page context received from frontend")
    
    try:
        # Get LLM Provider
        provider = db.query(LLMProvider).filter(LLMProvider.is_default == True, LLMProvider.is_enabled == True).first()
        if not provider:
            provider = db.query(LLMProvider).filter(LLMProvider.is_enabled == True).first()
        
        if not provider:
            raise HTTPException(status_code=503, detail="No LLM provider configured")
        
        # Get MCP client from connection pool (reuses existing connection)
        from app.services.mcp.pool import get_mcp_client
        
        mcp_client = None
        mcp_grafana_url = os.getenv("MCP_GRAFANA_URL")
        if mcp_grafana_url:
            try:
                mcp_client = await get_mcp_client(server_url=mcp_grafana_url)
            except Exception as e:
                logger.warning(f"Failed to get MCP client: {e}. Continuing without MCP support.")
        
        # Initialize services
        perm_service = AIPermissionService(db)
        
        # Initialize MCP-aware orchestrator
        orchestrator = ReviveOrchestrator(
            db=db,
            user=current_user,
            mcp_client=mcp_client,
            permission_service=perm_service,
            llm_provider=provider,
            alert_id=None
        )
        
        # Collect streamed response into a single response
        full_response = ""
        intent = "general"
        confidence = 0.0
        sources = []
        
        async for chunk in orchestrator.run_revive_turn(
            message=request.query,
            session_messages=[],
            page_context=request.page_context
        ):
            # Parse streamed chunks (they come as SSE format)
            if chunk.startswith("data: "):
                data_str = chunk[6:].strip()
                if data_str:
                    try:
                        data = json.loads(data_str)
                        chunk_type = data.get('type')
                        
                        if chunk_type == 'mode':
                            intent = data.get('content', 'general')
                        elif chunk_type == 'chunk':
                            full_response += data.get('content', '')
                        elif chunk_type == 'done':
                            sources = data.get('tool_calls', [])
                            confidence = 0.9  # High confidence if tools were used
                    except json.JSONDecodeError:
                        # Raw text chunk
                        full_response += chunk
            else:
                # Raw text chunk
                full_response += chunk
        
        # Note: Connection pool manages client lifecycle, no manual cleanup needed
        
        return AIHelperQueryResponse(
            response=full_response or "I apologize, but I couldn't generate a response.",
            session_id=request.session_id,
            intent=intent,
            confidence=confidence,
            sources=[{"type": "tool", "name": tool} for tool in sources] if sources else []
        )
        
    except Exception as e:
        logger.error(f"AI Helper query failed: {e}", exc_info=True)
        return AIHelperQueryResponse(
            response=f"I apologize, but I encountered an error processing your query: {str(e)}",
            session_id=request.session_id,
            confidence=0.0
        )


@router.post("/chat")
async def ai_helper_chat_deprecated(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    DEPRECATED: Use /api/troubleshoot/chat instead.
    
    This endpoint redirects to the new troubleshoot API for backwards compatibility.
    Will be removed in a future version.
    """
    from fastapi.responses import RedirectResponse
    from app.routers.troubleshoot_api import troubleshoot_chat
    
    logger.warning("Deprecated endpoint /api/ai-helper/chat called - please use /api/troubleshoot/chat")
    
    # Forward the request to the new endpoint
    return await troubleshoot_chat(request, db, current_user)
