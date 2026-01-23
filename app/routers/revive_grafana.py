"""
RE-VIVE Grafana Router

Dedicated to the Grafana-context workflow.
Integrates with MCP Client for external tools.
Strictly separated from other pillars.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import logging
import json
import os

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models import User, LLMProvider
from app.services.revive.orchestrator import ReviveOrchestrator
from app.services.ai_permission_service import AIPermissionService
from app.schemas_revive import AIHelperQueryRequest, AIHelperQueryResponse

# Unique prefix for this flow
router = APIRouter(
    prefix="/api/revive/grafana",
    tags=["revive-grafana"]
)

logger = logging.getLogger(__name__)

@router.post("/query", response_model=AIHelperQueryResponse)
async def revive_grafana_query(
    request: AIHelperQueryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Handle Grafana-context queries using MCP.
    """
    logger.info(f"RE-VIVE Grafana query from {current_user.username}: {request.query}")
    
    try:
        # Get LLM Provider
        provider = db.query(LLMProvider).filter(LLMProvider.is_default == True, LLMProvider.is_enabled == True).first()
        if not provider:
            provider = db.query(LLMProvider).filter(LLMProvider.is_enabled == True).first()
        
        if not provider:
            raise HTTPException(status_code=503, detail="No LLM provider configured")
            
        # Initialize MCP Client specific to this flow
        # Get MCP client from connection pool (reuses existing connection)
        from app.services.mcp.pool import get_mcp_client
        
        mcp_client = None
        mcp_grafana_url = os.getenv("MCP_GRAFANA_URL")
        
        if mcp_grafana_url:
            try:
                mcp_client = await get_mcp_client(server_url=mcp_grafana_url)
                logger.info("MCP Client attached to Grafana flow")
            except Exception as e:
                logger.warning(f"Failed to get MCP client: {e}. Grafana capabilities limited.")
        else:
             logger.warning("MCP_GRAFANA_URL not set. Grafana flow running without MCP.")
        
        # Initialize services
        perm_service = AIPermissionService(db)
        
        # Instantiate Orchestrator strictly with MCP
        orchestrator = ReviveOrchestrator(
            db=db,
            user=current_user,
            mcp_client=mcp_client, 
            permission_service=perm_service,
            llm_provider=provider,
            alert_id=None
        )
        
        full_response = ""
        intent = "grafana_help" # bias
        confidence = 0.0
        sources = []
        
        # Stream response
        async for chunk in orchestrator.run_revive_turn(
            message=request.query,
            session_messages=[], 
            page_context=request.page_context,
            explicit_mode="grafana_help" # Bias towards Grafana assistance
        ):
             # Parse streamed chunks
            if chunk.startswith("data: "):
                data_str = chunk[6:].strip()
                if data_str:
                    try:
                        data = json.loads(data_str)
                        chunk_type = data.get('type')
                        
                        if chunk_type == 'mode':
                            intent = data.get('content', 'grafana_help')
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
        logger.error(f"RE-VIVE Grafana query failed: {e}", exc_info=True)
        return AIHelperQueryResponse(
            response=f"Error processing query: {str(e)}",
            session_id=request.session_id,
            confidence=0.0
        )
