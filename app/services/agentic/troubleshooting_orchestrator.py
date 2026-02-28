import logging
import json
from typing import Optional, Dict, Any, List, AsyncGenerator
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import User, Alert, LLMProvider
from app.services.agentic.native_agent import NativeToolAgent, AgentResponse
from app.services.agentic.enhanced_tool_registry import EnhancedToolRegistry
from app.services.agentic.context_enricher import TroubleshootingContextEnricher
from app.services.mcp.client import MCPClient
from app.services.ai_permission_service import AIPermissionService

logger = logging.getLogger(__name__)

class TroubleshootingOrchestrator:
    """
    Orchestrates the troubleshooting process:
    1. Enriches context (Sift, OnCall, History)
    2. Configures tools (MCP + Native)
    3. Executes the NativeToolAgent
    """

    def __init__(
        self,
        db: Session,
        user: User,
        alert_id: Optional[UUID] = None,
        mcp_client: Optional[MCPClient] = None,
        permission_service: Optional[AIPermissionService] = None,
        llm_provider: Optional[LLMProvider] = None
    ):
        self.db = db
        self.user = user
        self.alert_id = alert_id
        self.mcp_client = mcp_client
        self.permission_service = permission_service
        self.llm_provider = llm_provider

    async def run_troubleshooting_turn(
        self, 
        message: str, 
        session_messages: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """
        Runs a single turn of the troubleshooting agent (streaming).
        Enriches context if this is the first message.
        """
        
        # 1. Context Enrichment (only if conversation is empty/start)
        # We assume if session_messages has only 1 item (the new user msg) or is empty, we enrich.
        # But usually session_messages includes history.
        system_context = ""
        if not session_messages and self.alert_id:
            try:
                enricher = TroubleshootingContextEnricher(self.db, self.mcp_client, self.alert_id)
                context = await enricher.enrich()
                
                system_context = f"""
## Context Enriched (Auto-Detected):
- **Sift Analysis:** {context.sift_analysis or 'N/A'}
- **OnCall:** {context.oncall_info or 'N/A'}
- **Similar Incidents:** {', '.join(context.similar_incidents) if context.similar_incidents else 'None'}
- **Summary:** {context.alert_summary}
"""
                logger.info("Context enriched for troubleshooting session")
            except Exception as e:
                logger.error(f"Context enrichment failed: {e}")

        # 2. Setup Registry Factory
        def registry_factory(db: Session, alert_id: Optional[UUID] = None):
            # We must use async initialize, but NativeToolAgent calls this in __init__ sync.
            # This is a problem. NativeToolAgent expects synchronous registry creation.
            # EnhancedToolRegistry needs async init for MCP.
            
            # WORKAROUND: We create the registry, and we force initialization if possible, 
            # or we accept that MCP tools might be loaded lazily or we need to change NativeToolAgent.
            
            # Since we can't change NativeToolAgent easily to be async init, 
            # we will assume EnhancedToolRegistry can be initialized later or specific tools are added dynamically.
            # But EnhancedToolRegistry stores tools in _tools dict.
            
            # Better approach: We create the registry HERE, fully initialized (via async), 
            # and pass a factory that returns this *already initialized* instance.
            return enhanced_registry

        # Initialize Registry
        enhanced_registry = EnhancedToolRegistry(
            db=self.db,
            alert_id=self.alert_id,
            mcp_client=self.mcp_client,
            user=self.user,
            permission_service=self.permission_service
        )
        
        # We need to await initialization of the registry
        await enhanced_registry.initialize()

        # 3. Initialize Agent
        # Pass the pre-computed system context as a hidden system message or prepend to user message?
        # NativeToolAgent generates its own system prompt.
        # We can append the system_context to the initial user message or insert a system message.
        
        messages_to_use = list(session_messages)
        if system_context:
            # Inject context as a system message at the start
            messages_to_use.insert(0, {"role": "system", "content": system_context})

        agent = NativeToolAgent(
            db=self.db,
            provider=self.llm_provider,
            alert=self.db.query(Alert).filter(Alert.id == self.alert_id).first() if self.alert_id else None,
            initial_messages=messages_to_use,
            registry_factory=registry_factory
        )

        # 4. Run/Stream
        async for chunk in agent.stream(message):
            yield chunk

        # 5. Capture tool calls (optional, for logging/orchestrator state)
        self.tool_calls_made = getattr(agent, 'tool_calls_made', [])
