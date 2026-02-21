import logging
import json
from typing import List, Dict, Any, AsyncIterator, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import User
from app.services.revive.mode_detector import ReviveModeDetector
from app.services.agentic.enhanced_tool_registry import EnhancedToolRegistry
from app.services.agentic.native_agent import NativeToolAgent
from app.services.revive.revive_agent import ReviveQuickHelpAgent  # RE-VIVE specific agent
from app.services.mcp.client import MCPClient
from app.services.ai_permission_service import AIPermissionService

logger = logging.getLogger(__name__)

class ReviveOrchestrator:
    """
    Orchestrates the RE-VIVE Unified Assistant workflow.
    
    Flow:
    1. Detect user intent/mode (Grafana vs AIOps).
    2. Initialize appropriate toolset.
    3. Execute agent loop.
    4. Stream responses.
    """

    def __init__(
        self,
        db: Session,
        user: User,
        mcp_client: MCPClient,
        permission_service: AIPermissionService,
        llm_provider: Any,  # LLMService
        alert_id: Optional[UUID] = None
    ):
        self.db = db
        self.user = user
        self.mcp_client = mcp_client
        self.permission_service = permission_service
        self.llm_provider = llm_provider
        self.alert_id = alert_id
        
        self.mode_detector = ReviveModeDetector()
        self.tool_calls_made = []

    async def run_revive_turn(
        self,
        message: str,
        session_messages: List[Dict[str, Any]],

        page_context: Optional[Dict[str, Any]] = None,
        explicit_mode: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Run a single turn of conversation.
        """
        # DEBUG: Log incoming page context
        logger.warning("=" * 80)
        logger.warning("🔍 REVIVE ORCHESTRATOR DEBUG: Incoming Request")
        logger.warning("=" * 80)
        logger.warning(f"User Message: {message}")
        if page_context:
            logger.warning(f"Page Context Received: YES")
            logger.warning(f"  - Page Type: {page_context.get('page_type', 'unknown')}")
            logger.warning(f"  - Page Title: {page_context.get('title', 'unknown')}")
            logger.warning(f"  - Client Tools Used: {page_context.get('client_tools_used', False)}")
            logger.warning(f"  - Has Page Specific Data: {bool(page_context.get('page_specific_data'))}")
            
            if page_context.get('page_specific_data'):
                psd = page_context['page_specific_data']
                logger.warning(f"  - Runbook ID: {psd.get('runbook_id', 'N/A')}")
                logger.warning(f"  - Steps Count: {len(psd.get('steps', []))}")
                logger.warning(f"  - PromQL Query: {psd.get('query', 'N/A')[:50] if psd.get('query') else 'N/A'}")
        else:
            logger.warning("Page Context Received: NO")
        logger.warning("=" * 80)
        
        # 1. Detect Mode with enhanced context
        current_page = page_context.get('url') if page_context else None
        
        mode_result = self.mode_detector.detect(
            message, 
            current_page=current_page,
            explicit_mode=explicit_mode,
            page_context=page_context,
            conversation_history=session_messages
        )
        logger.info(f"Detected mode: {mode_result.mode} (confidence: {mode_result.confidence:.2f}, intent: {mode_result.detected_intent})")
        
        # 2. Determine Tool Modules
        modules = self._get_modules_for_mode(mode_result.mode)
        
        # 3. Create Registry Factory
        # We need to initialize the registry (MCP tools fetching) asynchronously
        registry = EnhancedToolRegistry(
            db=self.db,
            alert_id=self.alert_id,
            mcp_client=self.mcp_client,
            user=self.user,
            permission_service=self.permission_service,
            modules=modules
        )
        await registry.initialize()
        
        # Factory that returns the same registry instance (ignores db/alert_id since already initialized)
        registry_factory = lambda db=None, alert_id=None: registry
        
        # 4. Initialize Agent
        # Note: We might want a specialized system prompt based on mode
        system_message = self._build_system_message(mode_result, page_context, len(session_messages))
        
        # DEBUG: Log system message content
        logger.warning("=" * 80)
        logger.warning("📋 SYSTEM MESSAGE SENT TO LLM")
        logger.warning("=" * 80)
        logger.warning(f"Mode: {mode_result.mode} | Confidence: {mode_result.confidence}")
        logger.warning(f"Session History Length: {len(session_messages)} messages")
        logger.warning(system_message['content'][:500] + "..." if len(system_message['content']) > 500 else system_message['content'])
        logger.warning("=" * 80)
        
        # Combine system message with history
        # Always use fresh system message for current context
        if session_messages and session_messages[0].get("role") == "system":
            # Replace old system message with updated one
            initial_messages = [system_message] + session_messages[1:]
        else:
            # Prepend new system message
            initial_messages = [system_message] + session_messages

        agent = ReviveQuickHelpAgent(
            db=self.db,
            provider=self.llm_provider,
            alert=None, # Not bound to alert necessarily
            initial_messages=initial_messages,
            registry_factory=registry_factory
        )
        
        # 5. Stream Response
        # We might yield a "mode_detected" event first
        yield f"data: {json.dumps({'type': 'mode', 'content': mode_result.mode})}\n\n"
        
        async for chunk in agent.stream(message):
            # NativeToolAgent yields JSON strings or raw text?
            # It yields "content" strings usually, or tool calls.
            # Wait, NativeToolAgent.stream yields raw chunks usually.
            # But troubleshoot_api wraps it in "data: ...".
            # Here we are inside the orchestrator using "yield".
            # The API router will likely wrap this.
            # But wait, troubleshoot_api wrapped chunks in json.
            # Let's check NativeToolAgent.stream output format.
            # Step 1000: `yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"` in API.
            # The orchestrator in Step 1000 yielded chunks.
            # So here I should yield chunks.
            yield chunk
            
        self.tool_calls_made = agent.tool_calls_made

    def _get_modules_for_mode(self, mode: str) -> List[str]:
        # RE-VIVE should have MINIMAL tools - just knowledge lookup
        # Troubleshooting mode (/ai) has the full tool set with observability
        base_modules = ['knowledge']  # Basic runbook/knowledge lookup only
        
        if mode == 'grafana':
            # For Grafana questions - just knowledge, no observability queries
            # User can use /ai if they want deep troubleshooting
            return base_modules + ['revive_grafana']
        elif mode == 'aiops':
            # For runbook/AIOps questions - knowledge only
            # NO observability module = no query_grafana_metrics, search_logs, etc.
            return base_modules + ['revive_aiops_helper']
        else:
            # Ambiguous - keep it minimal
            return base_modules

    def _build_system_message(self, mode_result, page_context: Optional[Dict[str, Any]] = None, history_length: int = 0):
        # Shared formatting instructions appended to every mode
        FORMATTING_INSTRUCTIONS = (
            "\n\n---\n"
            "## RESPONSE FORMATTING (MANDATORY)\n"
            "Always format your responses using Markdown so they render clearly in the chat UI:\n"
            "- **Bold** key terms, service names, and important values.\n"
            "- Use bullet lists (`-`) for options, steps, or findings.\n"
            "- Use numbered lists (`1.`) for sequential steps or procedures.\n"
            "- Use `inline code` for commands, file paths, config keys, and technical values.\n"
            "- Use fenced code blocks (``` ``` ```) for multi-line commands, scripts, or log snippets.\n"
            "- Use `##` or `###` headers to separate distinct sections in longer responses.\n"
            "- Use `>` blockquotes for important warnings or notes.\n"
            "- Keep responses concise — avoid walls of plain text.\n"
            "- Never output a response as a single unformatted paragraph if it contains multiple points.\n"
        )

        if mode_result.mode == 'grafana':
            content = (
                "You are the **RE-VIVE Assistant** (Quick Help Mode).\n\n"
                "You help users understand Grafana dashboards and PromQL/LogQL queries.\n"
                "You have access to basic Grafana knowledge.\n\n"
                "> If the user needs deep troubleshooting with live metrics or logs, suggest they use `/ai troubleshooting` instead."
            )
        elif mode_result.mode == 'aiops':
            content = (
                "You are **RE-VIVE**, a quick-help assistant for the AIOps Platform.\n\n"
                "## Your Role\n"
                "1. **Answer questions using the page context below** — if the information is visible on the page, use it directly.\n"
                "2. **Explain what's on the page** and guide users on what to do next.\n"
                "3. **Provide quick information** without making assumptions or taking unsolicited actions.\n\n"
                "## Critical Rules\n"
                "- If the user asks *how to* do something (execute, create, delete), explain the UI steps — **do NOT execute it**.\n"
                "- If runbook steps are in the page context below, **answer directly from that context** — do NOT call `get_runbook`.\n"
                "- For complex automated actions (execute runbook, troubleshoot, query live metrics), tell users:\n"
                "  > Use `/ai troubleshooting` for automated execution.\n"
                "- Only call tools if: (a) the answer is NOT in the page context, **and** (b) you need read-only information.\n\n"
                "## Available Tools (use sparingly)\n"
                "- `get_runbook` — only if the user asks about a runbook **not** currently displayed.\n"
                "- `show_available_runbooks` — only if the user asks *what runbooks exist?*\n"
                "- `show_available_servers` — only if the user asks *what servers are available?*\n"
            )
            if history_length > 0:
                content += f"\n\n> **Session Context**: This conversation has {history_length} previous messages."
        else:
            content = (
                "You are the **RE-VIVE Assistant** (Quick Help Mode).\n\n"
                "I can help you with quick questions about the current page.\n\n"
                "> For deep troubleshooting with live metrics and logs, suggest `/ai troubleshooting` instead."
            )
            if history_length > 0:
                content += f"\n\n> **Session Context**: This conversation has {history_length} previous messages."

        # Append shared formatting instructions to all modes
        content += FORMATTING_INSTRUCTIONS

        # Add Page Context if available
        if page_context:
            context_summary = f"\n\n[Current Context]\nUser is viewing: {page_context.get('title', 'Unknown Page')}"
            context_summary += f"\nURL: {page_context.get('url', 'Unknown')}"
            context_summary += f"\nPage Type: {page_context.get('page_type', 'unknown')}"
            
            # Check if client-side tools were used
            if page_context.get('client_tools_used'):
                context_summary += "\n\n✓ **Rich Context Available** (extracted via client-side tools)"
            
            # Add Page-Specific Data from Client Tools
            page_specific_data = page_context.get('page_specific_data')
            if page_specific_data:
                # Runbook Data
                if page_specific_data.get('runbook_id'):
                    context_summary += f"\n\n**Current Runbook (Loaded from Page)**"
                    context_summary += f"\nRunbook ID: {page_specific_data.get('runbook_id')}"
                    
                    metadata = page_specific_data.get('metadata', {})
                    if metadata.get('name'):
                        context_summary += f"\nName: {metadata['name']}"
                    if metadata.get('description'):
                        context_summary += f"\nDescription: {metadata['description']}"
                    
                    steps = page_specific_data.get('steps', [])
                    if steps:
                        context_summary += f"\n\n**Runbook Steps ({len(steps)} steps loaded):**"
                        for idx, step in enumerate(steps, 1):
                            context_summary += f"\n\nStep {idx}: {step.get('name', 'Unnamed')}"
                            if step.get('description'):
                                context_summary += f"\n  Description: {step['description']}"
                            if step.get('command_linux'):
                                cmd = step['command_linux'][:100] + '...' if len(step.get('command_linux', '')) > 100 else step.get('command_linux', '')
                                context_summary += f"\n  Command: {cmd}"
                            if step.get('target_os'):
                                context_summary += f"\n  OS: {step['target_os']}"
                        
                        context_summary += "\n\n**IMPORTANT:** You can answer questions about these steps directly without calling tools."
                
                # PromQL Query Data
                elif page_specific_data.get('query'):
                    context_summary += f"\n\n**PromQL Query (Extracted from Page)**"
                    context_summary += f"\nQuery: {page_specific_data['query']}"
                    context_summary += f"\nData Source: {page_specific_data.get('data_source', 'unknown')}"
                    context_summary += f"\nQuery Language: {page_specific_data.get('query_language', 'PromQL')}"
                    context_summary += "\n\n**IMPORTANT:** You can analyze this query directly."
                
                # Alert Data
                elif page_specific_data.get('alert_id'):
                    context_summary += f"\n\n**Current Alert (Loaded from Page)**"
                    context_summary += f"\nAlert ID: {page_specific_data['alert_id']}"
                    context_summary += f"\nAlert Name: {page_specific_data.get('alert_name', 'Unknown')}"
                    context_summary += f"\nSeverity: {page_specific_data.get('severity', 'unknown')}"
                    context_summary += f"\nStatus: {page_specific_data.get('status', 'unknown')}"
                    if page_specific_data.get('labels'):
                        context_summary += f"\nLabels: {page_specific_data['labels']}"
            
            # Fallback to legacy context extraction
            elif page_context.get('form_data') and page_context['form_data'].get('runbook_steps_summary'):
                context_summary += f"\n\n{page_context['form_data']['runbook_steps_summary']}"
            
            # Add general page text (truncated)
            elif page_context.get('page_text'):
                # Truncate to first 3000 chars to avoid token limit issues
                text_preview = page_context['page_text'][:3000]
                context_summary += f"\n\nPage Content Preview:\n{text_preview}"
                
            content += context_summary
            
        return {"role": "system", "content": content}
