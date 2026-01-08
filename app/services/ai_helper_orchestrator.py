"""
AI Helper Orchestrator - Core service with strict security controls
CRITICAL: Enforces action whitelist, no auto-execution, mandatory user approval
FIXED: Conversation history now persists across messages
"""
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from uuid import UUID, uuid4
from datetime import datetime
import logging
import json

from app.models_ai_helper import AIHelperConfig, AIHelperSession, KnowledgeSource
from app.models import User
from app.schemas_ai_helper import (
    AIHelperQuery,
    AIHelperResponse,
    AIAction,
    SessionType
)
from app.services.ai_audit_service import AIAuditService
from app.services.llm_service import LLMService
from app.services.knowledge_search_service import KnowledgeSearchService
from app.services.runbook_search_service import RunbookSearchService
from app.services.solution_ranker import SolutionRanker

logger = logging.getLogger(__name__)


# STRICT ACTION WHITELIST (Backend enforced)
ALLOWED_ACTIONS = {
    "suggest_form_values",
    "search_knowledge",
    "explain_concept",
    "show_example",
    "validate_input",
    "generate_preview",
    "chat"
}

# FORBIDDEN ACTIONS (Will be blocked)
BLOCKED_ACTIONS = {
    "execute_runbook",
    "ssh_connect",
    "submit_form",
    "api_call_modify",
    "auto_execute_any",
    "direct_db_access",
    "credential_access"
}


class AIHelperOrchestrator:
    """
    AI Helper Orchestrator with strict security controls
    Coordinates all AI operations while enforcing safety policies
    """

    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AIAuditService(db)
        self.llm_service = LLMService(db)
        self.knowledge_service = KnowledgeSearchService(db)

    async def process_query(
        self,
        user_id: UUID,
        query: str,
        session_id: Optional[UUID] = None,
        page_context: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AIHelperResponse:
        """
        Process user query with strict security controls
        Returns AI response with suggested actions (NO EXECUTION)
        """
        start_time = datetime.utcnow()
        correlation_id = uuid4()

        try:
            # Get user info
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            # Get or create session
            if not session_id:
                session_id = await self._create_session(user_id)
            else:
                # Validate session exists - if not, create a new one
                existing_session = self.db.query(AIHelperSession).filter(
                    AIHelperSession.id == session_id
                ).first()
                if not existing_session:
                    logger.warning(f"Session {session_id} not found, creating new session")
                    session_id = await self._create_session(user_id)

            # Get configuration
            config = await self._get_config()
            strict_mode = config.get('strict_mode', {}).get('value', True)

            # STEP 1: Assemble context
            context_start = datetime.utcnow()
            context = await self._assemble_context(query, page_context, session_id, user)
            context_assembly_ms = int((datetime.utcnow() - context_start).total_seconds() * 1000)

            # STEP 2: Call LLM
            llm_start = datetime.utcnow()
            llm_response = await self._call_llm(user, query, context)
            llm_latency_ms = int((datetime.utcnow() - llm_start).total_seconds() * 1000)

            # STEP 3: Parse LLM response
            ai_action, action_details, reasoning, confidence = await self._parse_llm_response(
                llm_response
            )

            # [VISIBILITY] Add Search Summary Footer
            try:
                search_summary = []
                if context.get('knowledge_chunks_used', 0) > 0:
                    search_summary.append(f"📚 Found {context.get('knowledge_chunks_used')} knowledge articles")
                
                if context.get('ranked_solutions'):
                     count = len(context['ranked_solutions'].get('solutions', []))
                     if count > 0:
                         search_summary.append(f"🛠️ Found {count} runbook solutions")
                
                if search_summary and action_details and "message" in action_details:
                    footer = "\n\n---\n*" + " | ".join(search_summary) + "*"
                    action_details["message"] += footer
            except Exception as e:
                logger.warning(f"Failed to append search summary: {e}")

            # [AUDIT] Store ranked solutions for analysis
            if context.get('ranked_solutions'):
                try:
                    action_details['solutions_presented'] = context['ranked_solutions'].get('solutions', [])
                    action_details['presentation_strategy'] = context['ranked_solutions'].get('presentation_strategy')
                except Exception as e:
                    logger.warning(f"Failed to store solutions for audit: {e}")

            # STEP 4: SECURITY CHECK - Validate action
            is_allowed, block_reason = await self._validate_action(ai_action)

            if not is_allowed:
                # LOG BLOCKED ACTION
                audit_log_id = await self.audit_service.log_ai_interaction(
                    user_id=user_id,
                    username=user.username,
                    user_query=query,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    page_context=page_context,
                    llm_provider=self.llm_service.provider,
                    llm_model=self.llm_service.model,
                    llm_request=self._sanitize_llm_request(context),
                    llm_response=llm_response,
                    llm_latency_ms=llm_latency_ms,
                    ai_suggested_action=ai_action,
                    ai_action_details=action_details,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    context_assembly_ms=context_assembly_ms
                )

                await self.audit_service.log_execution_result(
                    audit_log_id=audit_log_id,
                    executed=False,
                    action_blocked=True,
                    block_reason=block_reason
                )

                raise PermissionError(f"Action blocked: {block_reason}")

            # STEP 5: LOG INTERACTION (COMPREHENSIVE)
            audit_log_id = await self.audit_service.log_ai_interaction(
                user_id=user_id,
                username=user.username,
                user_query=query,
                session_id=session_id,
                correlation_id=correlation_id,
                page_context=page_context,
                llm_provider=self.llm_service.provider,
                llm_model=self.llm_service.model,
                llm_request=self._sanitize_llm_request(context),
                llm_response=llm_response,
                llm_tokens_input=llm_response.get('usage', {}).get('prompt_tokens'),
                llm_tokens_output=llm_response.get('usage', {}).get('completion_tokens'),
                llm_latency_ms=llm_latency_ms,
                llm_cost_usd=self._calculate_cost(llm_response),
                knowledge_sources_used=context.get('knowledge_sources_used'),
                knowledge_chunks_used=context.get('knowledge_chunks_used'),
                rag_search_time_ms=context.get('rag_search_time_ms'),
                code_files_referenced=context.get('code_files_referenced'),
                code_functions_referenced=context.get('code_functions_referenced'),
                ai_suggested_action=ai_action,
                ai_action_details=action_details,
                ai_confidence_score=confidence,
                ai_reasoning=reasoning,
                ip_address=ip_address,
                user_agent=user_agent,
                context_assembly_ms=context_assembly_ms
            )

            # STEP 6: Update session WITH CONVERSATION HISTORY (✅ FIXED)
            await self._update_session(session_id, query, llm_response, ai_action)

            # STEP 7: Build response
            response = AIHelperResponse(
                session_id=session_id,
                query_id=audit_log_id,
                action=AIAction(ai_action),
                action_details=action_details,
                reasoning=reasoning,
                confidence=confidence,
                requires_approval=True,  # ALWAYS requires approval in strict mode
                warning=self._generate_warning(ai_action, strict_mode)
            )

            total_duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            logger.info(
                f"Query processed: user={user.username}, action={ai_action}, "
                f"duration={total_duration_ms}ms"
            )

            return response

        except PermissionError as e:
            logger.warning(f"Action blocked for user {user_id}: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}", exc_info=True)

            # Log error
            try:
                await self.audit_service.log_ai_interaction(
                    user_id=user_id,
                    username=user.username if user else "unknown",
                    user_query=query,
                    session_id=session_id,
                    correlation_id=correlation_id,
                    page_context=page_context,
                    is_error=True,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    ip_address=ip_address,
                    user_agent=user_agent
                )
            except:
                pass

            raise

    async def _validate_action(self, action: str) -> Tuple[bool, Optional[str]]:
        """
        CRITICAL: Validate action against whitelist
        Returns: (is_allowed, block_reason)
        """
        # Check if action is explicitly blocked
        if action in BLOCKED_ACTIONS:
            return False, f"Action '{action}' is forbidden for security reasons"

        # Check if action is in whitelist
        if action not in ALLOWED_ACTIONS:
            return False, f"Action '{action}' is not in allowed action list"

        # Get runtime config
        config = await self._get_config()
        allowed_actions = config.get('allowed_actions', {}).get('value', list(ALLOWED_ACTIONS))
        blocked_actions = config.get('blocked_actions', {}).get('value', list(BLOCKED_ACTIONS))

        if action in blocked_actions:
            return False, f"Action '{action}' is blocked by system configuration"

        if action not in allowed_actions:
            return False, f"Action '{action}' is not enabled in system configuration"

        return True, None

    async def _assemble_context(
        self,
        query: str,
        page_context: Optional[Dict[str, Any]],
        session_id: UUID,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Assemble context for LLM
        Includes: knowledge base, code references, session history
        """
        context = {
            'query': query,
            'page_context': page_context,
            'knowledge_sources_used': [],
            'knowledge_chunks_used': 0,
            'rag_search_time_ms': 0,
            'code_files_referenced': [],
            'code_files_referenced': [],
            'code_functions_referenced': [],
            'session_history': [],
            'ranked_solutions': None
        }

        try:
            # Search knowledge base using semantic search
            rag_start = datetime.utcnow()
            knowledge_results = self.knowledge_service.search_similar(
                query=query,
                limit=5,
                app_id=page_context.get('app_id') if page_context else None
            )
            rag_time = int((datetime.utcnow() - rag_start).total_seconds() * 1000)
            
            logger.info(f"[RAG] Found {len(knowledge_results)} knowledge chunks in {rag_time}ms")

            context['knowledge_results'] = knowledge_results
            context['knowledge_chunks_used'] = len(knowledge_results)
            context['rag_search_time_ms'] = rag_time

            # NEW: Runbook search (parallel with knowledge search - conceptually)
            if user and self._is_troubleshooting_query(query, page_context):
                try:
                    runbook_service = RunbookSearchService(self.db)
                    runbook_results = await runbook_service.search_runbooks(
                        query=query,
                        context=page_context or {},
                        user=user,
                        limit=3
                    )
                    
                    if runbook_results:
                        ranker = SolutionRanker(self.db)
                        ranked_solutions = ranker.rank_and_combine_solutions(
                            runbooks=runbook_results,
                            manual_solutions=[],
                            knowledge_refs=knowledge_results,
                            user_context=page_context or {}
                        )
                        context['ranked_solutions'] = ranked_solutions.to_dict()
                        logger.info(f"Found {len(ranked_solutions.solutions)} solutions for troubleshooting query")
                except Exception as e:
                    logger.error(f"Error in solution search: {e}")

            # Get session history (✅ FIXED - retrieve from session.context)
            session = self.db.query(AIHelperSession).filter(
                AIHelperSession.id == session_id
            ).first()

            if session and session.context:
                context['session_history'] = session.context.get('history', [])[-10:]  # Last 10 messages (5 turns)

        except Exception as e:
            logger.warning(f"Error assembling context: {e}")

        return context

    def _is_troubleshooting_query(self, query: str, page_context: Optional[Dict] = None) -> bool:
        """Detect if this is a troubleshooting query that needs runbook search."""
        troubleshooting_keywords = [
            'high cpu', 'memory', 'disk', 'slow', 'error', 'fix', 'troubleshoot',
            'restart', 'down', 'failed', 'not working', 'issue', 'problem', 'crash',
            'latency', 'timeout', 'exception', 'bug', 'alert', 'incident',
            # Expanded for visibility/general search
            'search', 'find', 'lookup', 'how to', 'check', 'investigate', 'analyze', 'why', 'what is'
        ]
        
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in troubleshooting_keywords)

    async def _call_llm(
        self,
        user: User,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call LLM service with context
        """
        # Build system prompt
        system_prompt = self._build_system_prompt()

        # Build user message (✅ IMPROVED - better history formatting)
        user_message = self._build_user_message(query, context)

        # Call LLM
        response = await self.llm_service.generate_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1024,
            temperature=0.7
        )

        return response

    def _build_system_prompt(self) -> str:
        """
        Build system prompt for AI helper (✅ IMPROVED - better Grafana guidance)
        """
        return """You are an AI assistant for an AIOps platform integrated with Grafana.

Your role is to help users understand and configure the platform, but you CANNOT execute any actions directly.

ALLOWED ACTIONS:
- suggest_form_values: Suggest values for form fields
- search_knowledge: Search documentation and knowledge base
- explain_concept: Explain AIOps concepts and features (PREFERRED for PromQL help)
- show_example: Show examples of configurations
- validate_input: Validate user input
- generate_preview: Generate preview of configurations
- chat: Have a general conversation with the user

FORBIDDEN ACTIONS (You must NEVER suggest these):
- execute_runbook: Cannot execute runbooks
- ssh_connect: Cannot connect to servers
- submit_form: Cannot submit forms automatically
- api_call_modify: Cannot make API calls to modify data
- auto_execute_any: Cannot auto-execute anything

IMPORTANT RULES:
1. You can only SUGGEST actions, never execute them
2. User must always approve and execute manually
3. For form assistance, provide SPECIFIC field values in structured format
4. Never access credentials, execute commands, or modify data directly
5. Remember previous conversation context when responding
6. When suggesting PromQL queries, use the 'explain_concept' or 'chat' action with markdown code blocks for easy copying

SOLUTION PRESENTATION (Runbook-First Troubleshooting):
When context includes 'ranked_solutions':
  - You have been provided with pre-ranked solutions (runbooks + manual)
  - DO NOT re-rank or re-decide - use the ranking provided
  - Your job is to FORMAT these solutions into markdown
  - Follow the presentation_strategy from ranked_solutions:
      * 'single_solution': Show one clear recommendation
      * 'primary_with_alternatives': Lead with primary, mention alternatives exist
      * 'multiple_options': Show 2-3 options, let user choose
      * 'experimental_options': Show options but warn about low confidence
      * 'primary_plus_one': Show primary + one backup option

  Markdown Format Guidelines:
  - Use headings (## for sections, ### for options)
  - Use code blocks with language hints for commands
  - Use markdown links [Runbook Title](/runbooks/{id}) for runbooks. IMPORTANT: Use this exact link format.
  - Use simple text ratings (⭐⭐⭐ for confidence)
  - Use emojis sparingly (✅ for permissions, ⚠️ for warnings, 💡 for tips)
  - NO HTML, NO interactive buttons, NO forms
  - For Runbooks: Show permission status (✅ or 🔒) and success rate.

GRAFANA QUERY HANDLING (Multi-Datasource Support):
- Supports: Prometheus (PromQL), Loki (LogQL), Tempo (TraceQL), Mimir (PromQL)
- Check context for: query_language, data_source_type, builder_mode_detected
- If query extracted successfully:
  * Analyze based on query_language (PromQL, LogQL, or TraceQL)
  * Provide insights specific to the data source type
  * Show relevant examples and optimizations
- If builder_mode_detected is true:
  * Explain that Grafana is in Builder mode (visual query builder)
  * Recommend switching to Code mode for AI assistance: Click "Code" button in query editor
  * Offer to help write queries once they switch to Code mode
  * Still be helpful if they paste a query manually
- If query extraction failed:
  * Ask user to paste the query OR switch to Code mode
  * Offer to help write a new query based on their monitoring needs
  * Be specific about which query language based on data_source_type
- Always be helpful and proactive in offering query assistance for all Grafana stack components

EXAMPLES:

Example 1 - Suggesting form values for a runbook:
{
  "action": "suggest_form_values",
  "action_details": {
    "form_fields": {
      "name": "Apache2 Restart Runbook",
      "description": "Automatically restart Apache2 service when it fails"
    },
    "explanation": "These values will create a runbook. Copy them to the form."
  },
  "reasoning": "User requested a runbook to restart Apache2",
  "confidence": 0.9
}

Example 2 - General chat:
{
  "action": "chat",
  "action_details": {
    "message": "Hello! I can help you with creating runbooks, configuring alerts, understanding the platform features, and more. What would you like help with?"
  },
  "reasoning": "User greeted me",
  "confidence": 1.0
}

Example 3 - Explaining PromQL when query IS found:
{
  "action": "explain_concept",
  "action_details": {
    "concept": "PromQL Query Analysis",
    "explanation": "I can see your query monitors network traffic. To filter for a specific server, add the instance label like this:\\n\\n```promql\\nrate(node_network_transmit_bytes_total{instance=\\"server-name:9100\\"}[5m]) / 1024 / 1024\\n```\\n\\nReplace `server-name` with your actual server hostname or IP.\\n\\n**Key points:**\\n- The `{instance=\\"...\\"}` filter selects specific servers\\n- The `[5m]` is the time range for rate calculation\\n- Result is in MB/s"
  },
  "reasoning": "User asked about PromQL query targeting specific servers",
  "confidence": 0.95
}

Example 4 - Handling "Can you read this page?" in Builder mode:
{
  "action": "chat",
  "action_details": {
    "message": "I can see you're in Grafana's **Builder mode** (visual query builder). The AI Agent works best with queries in **Code mode**.\\n\\n**To get AI assistance:**\\n\\n1. 🔄 **Switch to Code mode** - Click the \\"Code\\" button in your query editor\\n2. 📋 **Or paste your query** - Copy your query and paste it here\\n\\n**Once in Code mode, I can:**\\n- Analyze your PromQL/LogQL/TraceQL queries\\n- Suggest optimizations and improvements\\n- Explain query syntax and behavior\\n- Help troubleshoot issues\\n\\n**Or I can help you write a query from scratch!** Just tell me what you want to monitor."
  },
  "reasoning": "User in Builder mode, extraction not possible",
  "confidence": 0.95
}

Example 5 - Handling query extraction failure (not Builder mode):
{
  "action": "chat",
  "action_details": {
    "message": "I can see you're on a Grafana query page, but I wasn't able to automatically extract the query from the editor. This can happen if:\\n\\n- The editor is still loading\\n- The query hasn't been entered yet\\n- The editor format isn't recognized\\n\\n**How I can help:**\\n\\n1. 📋 **Paste your query** - Copy the query and paste it here, and I'll analyze it\\n2. ✍️ **Describe your needs** - Tell me what you want to monitor and I'll help write a query\\n3. 📚 **Learn query languages** - I can explain PromQL, LogQL, or TraceQL\\n\\nWhat would you like to do?"
  },
  "reasoning": "Query extraction failed but not in Builder mode",
  "confidence": 0.9
}

Example 6 - Analyzing PromQL query (Prometheus/Mimir):
{
  "action": "explain_concept",
  "action_details": {
    "concept": "PromQL Query Analysis",
    "explanation": "I can see your **PromQL** query:\\n\\n```promql\\nup{instance=\\"remediation-engine:8080\\"}\\n```\\n\\n**What it does:**\\nThis query monitors the **uptime status** of a specific target. The `up` metric returns:\\n- `1` if target is reachable\\n- `0` if target is down\\n\\n**Current filter:**\\n- `instance=\\"remediation-engine:8080\\"` - Monitoring only this specific instance\\n\\n**Possible enhancements:**\\n\\n1. Monitor multiple instances:\\n```promql\\nup{instance=~\\"remediation-engine.*\\"}\\n```\\n\\n2. Alert on down instances:\\n```promql\\nup{instance=\\"remediation-engine:8080\\"} == 0\\n```\\n\\n3. Add job filter:\\n```promql\\nup{job=\\"app\\", instance=\\"remediation-engine:8080\\"}\\n```"
  },
  "reasoning": "Extracted PromQL query successfully from Code mode",
  "confidence": 1.0
}

Example 7 - Analyzing LogQL query (Loki):
{
  "action": "explain_concept",
  "action_details": {
    "concept": "LogQL Query Analysis",
    "explanation": "I can see your **LogQL** query for Loki:\\n\\n```logql\\n{job=\\"varlogs\\"} |= \\"error\\" | json\\n```\\n\\n**What it does:**\\n1. `{job=\\"varlogs\\"}` - Select log streams from 'varlogs' job\\n2. `|= \\"error\\"` - Filter lines containing \\"error\\" (case-sensitive)\\n3. `| json` - Parse logs as JSON\\n\\n**Possible improvements:**\\n\\n1. Case-insensitive search:\\n```logql\\n{job=\\"varlogs\\"} |~ \\"(?i)error\\" | json\\n```\\n\\n2. Count errors per minute:\\n```logql\\nsum(count_over_time({job=\\"varlogs\\"} |= \\"error\\" [1m]))\\n```\\n\\n3. Extract JSON fields:\\n```logql\\n{job=\\"varlogs\\"} | json | level=\\"error\\"\\n```"
  },
  "reasoning": "Detected LogQL query from Loki data source",
  "confidence": 1.0
}

Response format (JSON):
{
  "action": "one of the allowed actions",
  "action_details": {detailed action data},
  "reasoning": "why you suggest this",
  "confidence": 0.0 to 1.0
}"""

    def _build_user_message(self, query: str, context: Dict[str, Any]) -> str:
        """
        Build user message with context (✅ IMPROVED - better history formatting)
        """
        message_parts = []
        
        # Add ranked solutions FIRST if available
        if context.get('ranked_solutions'):
            solutions_data = context['ranked_solutions']
            message_parts.append("## Determined Solutions (Use these to answer):")
            message_parts.append(json.dumps(solutions_data, indent=2))
            message_parts.append("\nFormat the above solutions into markdown based on presentation_strategy.\n")

        # Add conversation history FIRST if available (✅ CRITICAL for context continuity)
        if context.get('session_history'):
            message_parts.append("## Previous Conversation:")
            for msg in context['session_history'][-6:]:  # Last 6 messages (3 turns)
                role = msg.get('role', 'user').capitalize()
                content = msg.get('content', '')
                # Truncate long messages
                if len(content) > 500:
                    content = content[:500] + "..."
                message_parts.append(f"{role}: {content}")
            message_parts.append("\n---\n")

        # Current query
        message_parts.append(f"## Current User Query:\n{query}")

        # Add page context
        if context.get('page_context'):
            page_info = context['page_context']
            message_parts.append(f"\n## Current Page Context:")
            message_parts.append(f"URL: {page_info.get('url', 'unknown')}")
            message_parts.append(f"Page Type: {page_info.get('page_type', 'unknown')}")
            if page_info.get('form_id'):
                message_parts.append(f"Form ID: {page_info.get('form_id')}")
            
            # Add form data if present (includes queries!)
            form_data = page_info.get('form_data', {})
            if form_data:
                # Detect query language
                query_language = form_data.get('query_language', 'PromQL')
                data_source = form_data.get('data_source_type', 'unknown')

                message_parts.append("\n## Form Data on Page:")
                for key, value in form_data.items():
                    if value:  # Only add non-empty values
                        # Special formatting for queries
                        if key in ['query', 'promql_query'] and not isinstance(value, bool):
                            # Use detected query language for syntax highlighting
                            lang_hint = query_language.lower().replace('ql', '')  # promql -> prom, logql -> log
                            message_parts.append(f"\n**{query_language} Query** (Data source: {data_source}):\n```{lang_hint}\n{value}\n```")
                        elif key not in ['extraction_method', 'query_language', 'data_source_type', 'builder_mode_detected', 'query_extraction_failed']:
                            # Skip internal metadata fields
                            message_parts.append(f"- {key}: {value}")
                            
            # Add Grafana Context (✅ IMPROVED - Multi-datasource & Builder mode support)
            if page_info.get('is_grafana'):
                message_parts.append("\n## Grafana Context:")
                message_parts.append(f"- Is Grafana Page: Yes")

                # Add data source information
                query_language = form_data.get('query_language', 'PromQL')
                data_source = form_data.get('data_source_type', 'unknown')
                if data_source != 'unknown':
                    message_parts.append(f"- Data Source: {data_source.capitalize()}")
                    message_parts.append(f"- Query Language: {query_language}")

                if page_info.get('grafana_title'):
                    message_parts.append(f"- Dashboard Title: {page_info.get('grafana_title')}")
                if page_info.get('grafana_url'):
                    message_parts.append(f"- Internal URL: {page_info.get('grafana_url')}")

                # Check if query was extracted successfully
                has_query = False
                for key in form_data.keys():
                    if key in ['query', 'promql_query']:
                        val = form_data.get(key)
                        if val and not isinstance(val, bool):
                            has_query = True
                            break

                if page_info.get('is_native_grafana'):
                    message_parts.append("\n**CONTEXT:** Running natively inside Grafana with DOM access.")

                    # Check for Builder mode
                    builder_mode = form_data.get('builder_mode_detected', False)

                    if builder_mode:
                        message_parts.append("⚠️ **BUILDER MODE DETECTED** - User is in visual query builder")
                        message_parts.append("\n**IMPORTANT INSTRUCTION:**")
                        message_parts.append("- Explain that AI Agent works best in Code mode")
                        message_parts.append("- Guide user to click the 'Code' button in the query editor")
                        message_parts.append("- Offer to help write queries from scratch if they describe what they want")
                        message_parts.append("- Still accept pasted queries if user provides them")
                    elif has_query:
                        extraction_method = form_data.get('extraction_method', 'unknown')
                        message_parts.append(f"✅ Successfully extracted {query_language} query via: {extraction_method}")
                    else:
                        message_parts.append("⚠️ No query detected in editor. Possible reasons:")
                        message_parts.append("  - Editor is empty")
                        message_parts.append("  - Editor hasn't loaded yet")
                        message_parts.append("  - Query is in an unsupported format")

                        if form_data.get('query_extraction_failed'):
                            message_parts.append(f"\n**SUGGESTION:** Ask user to:")
                            message_parts.append(f"1. Paste their {query_language} query directly in the chat")
                            message_parts.append("2. Or tell you what they want to query and you can help write it")
                        else:
                            message_parts.append("\nIf user is asking about a specific query, politely ask them to paste it in the chat.")

                elif page_info.get('grafana_access_error'):
                    message_parts.append("\n**NOTE:** Unable to read Grafana content due to cross-origin restrictions.")
                    message_parts.append(f"Ask user to paste the {query_language} query in the chat.")
                else:
                    message_parts.append("\n**NOTE:** Connected via Proxy. Query extraction may be limited.")
                    if not has_query:
                        message_parts.append(f"Ask user to paste the {query_language} query if they want help with it.")

            # Add Server Context for troubleshooting (WinRM/SSH awareness)
            server_id = page_info.get('server_id')
            server_protocol = page_info.get('server_protocol') or page_info.get('protocol')
            server_os_type = page_info.get('server_os_type') or page_info.get('os_type')
            
            # If we have a server_id but no os_type, try to look it up
            if server_id and not server_os_type:
                try:
                    from app.models import ServerCredential
                    server = self.db.query(ServerCredential).filter(
                        ServerCredential.id == server_id
                    ).first()
                    if server:
                        server_protocol = getattr(server, 'protocol', 'ssh') or 'ssh'
                        server_os_type = getattr(server, 'os_type', None)
                        # Infer OS from protocol if not set
                        if not server_os_type:
                            server_os_type = 'windows' if server_protocol == 'winrm' else 'linux'
                except Exception as e:
                    logger.debug(f"Could not look up server: {e}")
            
            # If we have any server context, add it to the message
            if server_protocol or server_os_type:
                message_parts.append("\n## Server Context:")
                if server_os_type:
                    message_parts.append(f"- **OS Type**: {server_os_type.upper()}")
                if server_protocol:
                    message_parts.append(f"- **Protocol**: {server_protocol}")
                
                if server_os_type and server_os_type.lower() == 'windows':
                    message_parts.append("\n**IMPORTANT**: This is a **WINDOWS** server.")
                    message_parts.append("- Use **PowerShell** or **CMD** commands (Get-Volume, Get-Process, wmic, systeminfo)")
                    message_parts.append("- Do NOT suggest Linux commands (df, ps, top, free, etc.)")
                elif server_os_type and server_os_type.lower() == 'linux':
                    message_parts.append("\n**IMPORTANT**: This is a **LINUX** server.")
                    message_parts.append("- Use **bash/shell** commands (df, ps, top, free, etc.)")

        # Add knowledge results
        if context.get('knowledge_results'):
            message_parts.append("\n## Relevant Documentation:")
            for i, result in enumerate(context['knowledge_results'][:3], 1):
                content = result.get('content', '')[:200]
                message_parts.append(f"{i}. {content}...")

        return "\n".join(message_parts)

    async def _parse_llm_response(
        self,
        llm_response: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any], str, float]:
        """
        Parse LLM response to extract action, details, reasoning, confidence
        """
        try:
            response_data = {}
            content = llm_response.get('choices', [{}])[0].get('message', {}).get('content', '{}')

            # Try to parse as JSON
            try:
                # If wrapped in JSON manually (sometimes small models do this)
                if isinstance(content, str) and content.strip().startswith('{'):
                    # Try to extract JSON from markdown block if present
                    if "```json" in content:
                        json_str = content.split("```json")[1].split("```")[0].strip()
                        response_data = json.loads(json_str)
                    elif "```" in content:
                        # Try any code block
                        json_str = content.split("```")[1].strip()
                        if json_str.startswith('json'):
                            json_str = json_str[4:].strip()
                        response_data = json.loads(json_str)
                    else:
                        response_data = json.loads(content)
                else:
                    # Assume it's already a dict if not a string starting with '{'
                    # This path might be taken if llm_response.content is already a dict
                    # or if the LLM response object itself is structured.
                    # For consistency with the original, we'll try to parse the 'content' string.
                    pass # If content is not a string starting with '{', response_data remains empty for now.
            except Exception:
                pass

            # Fallback if parsing failed or response_data is still empty
            if not response_data:
                # Treat as simple chat
                response_data = {
                    "action": "chat",
                    "action_details": {"message": content},
                    "reasoning": "Parsed as direct response",
                    "confidence": 0.8
                }

            action = response_data.get('action', 'chat')
            action_details = response_data.get('action_details', {})
            reasoning = response_data.get('reasoning', '')
            confidence = response_data.get('confidence', 0.5)

            return action, action_details, reasoning, confidence

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return "chat", {"message": "I encountered an error processing your request.", "error": str(e)}, "Error fallback", 0.0

    async def _create_session(self, user_id: UUID) -> UUID:
        """Create new AI helper session"""
        session = AIHelperSession(
            user_id=user_id,
            session_type='general',
            status='active',
            context={'history': []}  # ✅ Initialize with empty history
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session.id

    async def _update_session(
        self,
        session_id: UUID,
        user_query: str,              # ✅ FIXED: Need the query
        llm_response: Dict[str, Any],
        ai_action: str                # ✅ FIXED: Need the action
    ):
        """
        Update session with latest interaction (✅ FIXED - now saves conversation history)
        """
        session = self.db.query(AIHelperSession).filter(
            AIHelperSession.id == session_id
        ).first()

        if session:
            session.last_activity_at = datetime.utcnow()
            session.total_queries += 1
            session.total_tokens_used += llm_response.get('usage', {}).get('total_tokens', 0)
            cost_float = self._calculate_cost(llm_response)
            session.total_cost_usd += Decimal(str(cost_float))

            # ✅ CRITICAL FIX: Save conversation history to session.context
            if not session.context:
                session.context = {'history': []}

            history = session.context.get('history', [])

            # Add user query
            history.append({
                'role': 'user',
                'content': user_query,
                'timestamp': datetime.utcnow().isoformat()
            })

            # Add AI response
            llm_content = ""
            if llm_response.get('choices'):
                llm_content = llm_response['choices'][0].get('message', {}).get('content', '')

            history.append({
                'role': 'assistant',
                'content': llm_content,
                'action': ai_action,
                'timestamp': datetime.utcnow().isoformat()
            })

            # Keep only last 20 messages (10 conversation turns)
            session.context['history'] = history[-20:]
            
            # Force SQLAlchemy to detect change in JSON field
            flag_modified(session, "context")

            self.db.commit()
            logger.debug(f"Session {session_id} updated with conversation history (total messages: {len(session.context['history'])})")

    async def _get_config(self) -> Dict[str, Any]:
        """Get AI helper configuration"""
        configs = self.db.query(AIHelperConfig).filter(
            AIHelperConfig.enabled == True
        ).all()

        config_dict = {}
        for config in configs:
            config_dict[config.config_key] = {
                'value': config.config_value,
                'description': config.description
            }

        return config_dict

    def _sanitize_llm_request(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize LLM request before logging (remove sensitive data)"""
        sanitized = context.copy()
        # Remove full content, keep only metadata
        if 'knowledge_results' in sanitized:
            sanitized['knowledge_results'] = f"{len(sanitized['knowledge_results'])} results"
        if 'session_history' in sanitized:
            sanitized['session_history'] = f"{len(sanitized['session_history'])} messages"
        return sanitized

    def _calculate_cost(self, llm_response: Dict[str, Any]) -> float:
        """Calculate cost of LLM call"""
        # Simplified cost calculation
        # TODO: Implement actual pricing based on provider
        tokens = llm_response.get('usage', {}).get('total_tokens', 0)
        cost_per_1k = 0.002  # Example: $0.002 per 1K tokens
        return (tokens / 1000) * cost_per_1k

    def _generate_warning(self, action: str, strict_mode: bool) -> Optional[str]:
        """Generate warning message based on action"""
        if strict_mode:
            return "This is a suggestion only. You must review and approve before any action is taken."
        return None
