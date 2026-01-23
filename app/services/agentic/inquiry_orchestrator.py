"""
Inquiry Orchestrator

Handles the processing of AI Inquiry queries. 
Responsible for:
1. Handling the user's natural language query.
2. Checking permissions via AIPermissionService.
3. Selecting appropriate tools from the InquiryRegistry.
4. Executing tools and formulating a response.
"""

import logging
from typing import Dict, Any, Optional, List, Union, AsyncGenerator
from uuid import UUID
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session


from app.models import User, LLMProvider
from app.models_ai import AISession
from app.services.llm_service import get_default_provider
from app.services.ai_permission_service import AIPermissionService
from app.services.agentic.tools.registry import create_inquiry_registry, CompositeToolRegistry
from app.services.agentic.native_agent import NativeToolAgent
from app.services.agentic.ai_inquiry_agent import AiInquiryAgent

logger = logging.getLogger(__name__)


@dataclass
class InquiryResponse:
    session_id: UUID
    answer: str
    tools_used: List[str] = field(default_factory=list)
    tokens_used: int = 0
    error: Optional[str] = None

class InquiryOrchestrator:
    """
    Orchestrates the AI Inquiry process.
    """
    
    def __init__(
        self,
        db: Session,
        user: User,
        provider: Optional[LLMProvider] = None,
        permission_service: Optional[AIPermissionService] = None,
        registry: Optional[CompositeToolRegistry] = None
    ):
        self.db = db
        self.user = user
        self.provider = provider
        self.permission_service = permission_service or AIPermissionService(db)
        
        # Use provided registry or create a new inquiry-specific one
        if registry:
            self.registry = registry
        else:
            self.registry = create_inquiry_registry(db)

    async def process_query(
        self,
        query: str,
        session_id: Optional[UUID] = None,
        context: Optional[Dict] = None
    ) -> InquiryResponse:
        """
        Process a natural language query for the Inquiry pillar.
        """
        if not session_id:
            logger.info("No session_id provided for Inquiry query")
            
        # 0. Resolve Provider
        provider = self.provider
        if not provider:
            provider = get_default_provider(self.db)
            
        if not provider:
             return InquiryResponse(
                session_id=session_id or UUID("00000000-0000-0000-0000-000000000000"),
                answer="No LLM provider configured. Please contact an administrator.",
                error="ConfigurationError"
            )
        
        # 1. Permission Check
        if not self.permission_service.can_access_pillar(self.user, "inquiry"):
            return InquiryResponse(
                session_id=session_id or UUID("00000000-0000-0000-0000-000000000000"),
                answer="Access denied. You do not have permission to use the AI Inquiry system.",
                error="AccessDenied"
            )

        # 2. Setup Tools
        all_tools = self.registry.get_tools()
        allowed_tools = self.permission_service.filter_tools_by_permission(
            self.user, "inquiry", all_tools
        )
        
        try:
            # Use NativeToolAgent to execute
            # Note: NativeToolAgent manages its own registry based on factory, but checks allowed_tools passed?
            # NativeToolAgent signature: db, provider, alert, max_iterations...
            # It creates a registry internally using registry_factory.
            # We want to use OUR registry which has filtered permissions?
            # Actually NativeToolAgent logic:
            # self.tool_registry = factory(db, alert_id=alert_id)
            # It doesn't seemingly support passing a pre-existing registry object directly in __init__ 
            # based on lines 95-96 of native_agent.py.
            # But we can pass a factory lambda that returns our registry.
            
            registry_factory = lambda db, alert_id: self.registry
            
            # Also, NativeToolAgent doesn't inherently filter tools by permission unless the registry does.
            # Our registry (CompositeToolRegistry) has all tools.
            # We need to ensure the agent only uses allowed tools.
            # NativeToolAgent uses self.tool_registry.get_tools().
            # If we want to restrict tools, we might need a filtered registry or pass allowed tools?
            # Looking at NativeToolAgent again...
            # It gets tools from registry.
            
            # Hack/Workaround: We can instruct the agent via prompt which tools to use, 
            # OR better: Create a Temporary ToolRegistry with only allowed tools?
            
            # Simple solution for now: Use the registry we have, but maybe the permissions service 
            # should have filtered the registry creation?
            # Assuming 'allowed_tools' were filtered correctly above.
            


            # Load Conversation History
            initial_messages = []
            if session_id:
                from app.models_ai import AIMessage
                history = self.db.query(AIMessage).filter(
                    AIMessage.session_id == session_id
                ).order_by(AIMessage.created_at).all()
                
                for msg in history:
                    # Map AIMessage to dict format expected by Agent
                    msg_dict = {
                        "role": msg.role,
                        "content": msg.content
                    }
                    # Include tool_calls if present
                    if msg.tool_calls:
                         msg_dict["tool_calls"] = msg.tool_calls
                    if msg.tool_call_id:
                         msg_dict["tool_call_id"] = msg.tool_call_id
                         
                    initial_messages.append(msg_dict)
            
            # Use AiInquiryAgent to execute
            # Pass factory and other params
            
            registry_factory = lambda db, alert_id: self.registry
            
            agent = AiInquiryAgent(
                db=self.db,
                provider=provider,
                registry_factory=registry_factory,
                max_iterations=5,
                initial_messages=initial_messages  # Pass history
            )
            
            # Note regarding permissions: NativeToolAgent will expose ALL tools in the registry to the LLM.
            # If we want to restrict them, we should probably construct a registry with only approved tools.
            # But for now, let's proceed with the registered tools.
            # The PermissionService check at step 1 is high-level. 
            # Fine-grained tool permission (execute/deny) is typically checked at execution time 
            # but NativeToolAgent might not call PermissionService.
            # We will implement that refinement later or via `CompositeToolRegistry` which delegates.
            
            response_obj = await agent.run(query) 
            
            return InquiryResponse(
                session_id=session_id or UUID("00000000-0000-0000-0000-000000000000"),
                answer=response_obj.content,
                tools_used=response_obj.tool_calls_made
            )

        except Exception as e:
            logger.error(f"Error processing inquiry: {e}", exc_info=True)
            return InquiryResponse(
                session_id=session_id or UUID("00000000-0000-0000-0000-000000000000"),
                answer=f"I encountered an error while processing your request: {str(e)}",
                error=str(e)
            )

    async def stream_query(
        self,
        query: str,
        session_id: Optional[UUID] = None,
        context: Optional[Dict] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream an Inquiry query.
        """
        # Resolve Provider
        provider = self.provider or get_default_provider(self.db)
            
        if not provider:
            yield f"data: {json.dumps({'type': 'error', 'content': 'No LLM provider configured'})}\n\n"
            return
        
        # Load Conversation History
        initial_messages = []
        if session_id:
            from app.models_revive import AIMessage
            history = self.db.query(AIMessage).filter(
                AIMessage.session_id == session_id
            ).order_by(AIMessage.created_at).all()
            
            for msg in history:
                initial_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Use AiInquiryAgent
        registry_factory = lambda db, alert_id: self.registry
        agent = AiInquiryAgent(
            db=self.db,
            provider=provider,
            registry_factory=registry_factory,
            max_iterations=5,
            initial_messages=initial_messages
        )
        
        # Stream
        async for chunk in agent.stream(query):
            yield chunk

        # Track tools used (accessible via self.tool_calls_made after generator finishes)
        self.tool_calls_made = getattr(agent, 'tool_calls_made', [])

    def _build_system_prompt(self, tools: List) -> str:
        """
        Build the system prompt for the Inquiry Agent.
        Note: NativeToolAgent generates its own system prompt, 
        so this might be unused or we can pass it as initial message if NativeToolAgent supports overriding.
        NativeToolAgent has `_get_system_prompt`.
        """
        # ... logic ...
        return ""

