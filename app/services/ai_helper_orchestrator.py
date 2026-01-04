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

            # Get configuration
            config = await self._get_config()
            strict_mode = config.get('strict_mode', {}).get('value', True)

            # STEP 1: Assemble context
            context_start = datetime.utcnow()
            context = await self._assemble_context(query, page_context, session_id)
            context_assembly_ms = int((datetime.utcnow() - context_start).total_seconds() * 1000)

            # STEP 2: Call LLM
            llm_start = datetime.utcnow()
            llm_response = await self._call_llm(user, query, context)
            llm_latency_ms = int((datetime.utcnow() - llm_start).total_seconds() * 1000)

            # STEP 3: Parse LLM response
            ai_action, action_details, reasoning, confidence = await self._parse_llm_response(
                llm_response
            )

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
        session_id: UUID
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
            'code_functions_referenced': [],
            'session_history': []
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

            # Get session history (✅ FIXED - retrieve from session.context)
            session = self.db.query(AIHelperSession).filter(
                AIHelperSession.id == session_id
            ).first()

            if session and session.context:
                context['session_history'] = session.context.get('history', [])[-10:]  # Last 10 messages (5 turns)

        except Exception as e:
            logger.warning(f"Error assembling context: {e}")

        return context

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
        Build system prompt for AI helper (✅ IMPROVED - better form guidance)
        """
        return """You are an AI assistant for an AIOps platform.

Your role is to help users understand and configure the platform, but you CANNOT execute any actions directly.

ALLOWED ACTIONS:
- suggest_form_values: Suggest values for form fields
- search_knowledge: Search documentation and knowledge base
- explain_concept: Explain AIOps concepts and features
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

EXAMPLES:

Example 1 - Suggesting form values for a runbook:
{
  "action": "suggest_form_values",
  "action_details": {
    "form_fields": {
      "name": "Apache2 Restart Runbook",
      "description": "Automatically restart Apache2 service when it fails",
      "server": "t-aisop-01",
      "steps": [
        {"command": "systemctl status apache2", "description": "Check current status"},
        {"command": "systemctl restart apache2", "description": "Restart service"},
        {"command": "systemctl status apache2", "description": "Verify restart succeeded"}
      ],
      "notification_enabled": true
    },
    "explanation": "These values will create a runbook to restart Apache2 on server t-aisop-01. The user needs to fill these values in the form and click 'Create'."
  },
  "reasoning": "User requested a runbook to restart Apache2 on t-aisop-01",
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

Example 3 - Explaining a concept:
{
  "action": "explain_concept",
  "action_details": {
    "concept": "runbooks",
    "explanation": "Runbooks are automated remediation scripts that execute predefined steps to resolve issues. They can check service status, restart services, or perform other maintenance tasks."
  },
  "reasoning": "User asking about what runbooks are",
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
            content = llm_response.get('choices', [{}])[0].get('message', {}).get('content', '{}')

            # Try to parse as JSON
            try:
                parsed = json.loads(content)
            except:
                # Fallback: extract JSON from markdown code block
                if '```json' in content:
                    json_str = content.split('```json')[1].split('```')[0].strip()
                    parsed = json.loads(json_str)
                elif '```' in content:
                    # Try any code block
                    json_str = content.split('```')[1].strip()
                    if json_str.startswith('json'):
                        json_str = json_str[4:].strip()
                    parsed = json.loads(json_str)
                else:
                    # Default fallback - treat as chat
                    parsed = {
                        "action": "chat",
                        "action_details": {"message": content},
                        "reasoning": "Providing conversational response",
                        "confidence": 0.7
                    }

            action = parsed.get('action', 'chat')
            action_details = parsed.get('action_details', {})
            reasoning = parsed.get('reasoning', '')
            confidence = parsed.get('confidence', 0.5)

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
