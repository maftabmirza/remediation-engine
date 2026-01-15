"""
RE-VIVE Orchestrator
"""
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID
import json
from sqlalchemy.orm import Session

from app.models import User
from app.services.observability_orchestrator import get_observability_orchestrator, ObservabilityQueryResult
from app.services.runbook_search_service import get_runbook_search_service
from app.services.ai_audit_service import get_ai_audit_service
from app.services.llm_service import generate_completion
from app.services.prompt_service import PromptService
from app.models_revive import AISession, AIMessage

logger = logging.getLogger(__name__)

class ReviveOrchestrator:
    """
    Orchestrates RE-VIVE AI Assistant interactions.
    Routes queries to appropriate subsystems (Observability, Knowledge Base, etc.)
    and manages conversation state.
    """

    def __init__(self):
        self.observability = get_observability_orchestrator()
        self.runbook_search = get_runbook_search_service()
        self.audit = get_ai_audit_service()

    async def processed_query(
        self,
        db: Session,
        query: str,
        user: User,
        session_id: Optional[str] = None,
        context: Optional[dict] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for AI queries.
        """
        # 1. Manage Session
        session = self._get_or_create_session(db, session_id, user.id, context)
        
        # 2. Log User Message
        user_msg = AIMessage(
            session_id=session.id,
            role="user",
            content=query
        )
        db.add(user_msg)
        db.commit()

        response_text = ""
        sources = []
        confidence = 0.0
        intent = "unknown"

        # 3. Determine Intent & Execute
        # Use LLM 'Router' to decide what to do
        routing_decision = await self._determine_intent_with_llm(db, query, context)
        intent = routing_decision.get("intent", "general")
        confidence = float(routing_decision.get("confidence", 0.0))
        reasoning = routing_decision.get("reasoning", "")
        
        logger.info(f"LLM Routing Decision: {intent} (conf: {confidence}). Reasoning: {reasoning}")

        if intent == "remediation":
            runbooks = self.runbook_search.search(db, query)
            if runbooks:
                response_text = f"I found {len(runbooks)} relevant runbooks based on your request:\n\n"
                for rb in runbooks:
                    response_text += f"- **{rb.name}**: {rb.description}\n"
                    sources.append({"type": "runbook", "id": str(rb.id), "name": rb.name})
            else:
                # Fallback to general if runbooks not found
                intent = "general"
                
        elif intent == "observability":
            # Delegate to observability orchestrator
            obs_result = await self.observability.query(query)
            
            # Improvement #5: Richer observability responses with data snippets
            response_text = f"**Observability Query Results**\n\n"
            response_text += f"📊 **Query:** `{obs_result.original_query}`\n\n"
            
            if obs_result.total_logs > 0:
                response_text += f"📝 **Logs:** Found {obs_result.total_logs} log entries.\n"
                # Include first few log snippets if available
                if hasattr(obs_result, 'log_samples') and obs_result.log_samples:
                    response_text += "```\n"
                    for log in obs_result.log_samples[:3]:
                        response_text += f"{log}\n"
                    response_text += "```\n"
                    
            if obs_result.total_metrics > 0:
                response_text += f"📈 **Metrics:** Found matching metrics.\n"
                # Include metric values if available
                if hasattr(obs_result, 'metric_samples') and obs_result.metric_samples:
                    for metric in obs_result.metric_samples[:5]:
                        response_text += f"- {metric}\n"
            
            if obs_result.total_logs == 0 and obs_result.total_metrics == 0:
                response_text += "⚠️ No data found for this query. Try adjusting your time range or query parameters.\n"
                
            sources.append({"type": "observability", "query": obs_result.original_query})

        # Final Fallback / General Intent
        if not response_text or intent == "general":
            intent = "general_context_aware"
            try:
                # Add the routing reasoning to the prompt context so the answerer knows WHY it was called
                if context is None:
                    context = {}
                context['routing_reasoning'] = reasoning
                
                prompt = PromptService.get_ai_helper_prompt(query, context)
                llm_response, _ = await generate_completion(db, prompt)
                response_text = llm_response
            except Exception as e:
                logger.error(f"LLM generation failed: {e}", exc_info=True)
                response_text = "I apologize, but I'm having trouble connecting to my AI brain right now. Please try again later."
                confidence = 0.0

        # Improvement #4: Builder Mode Guidance
        if context and context.get('form_data', {}).get('builder_mode_detected'):
            response_text += "\n\n💡 **Tip:** You're in Builder mode. Switch to **Code mode** for more precise query assistance."

        # 4. Log Assistant Response
        assistant_msg = AIMessage(
            session_id=session.id,
            role="assistant",
            content=response_text,
            metadata_json={"intent": intent, "confidence": confidence, "sources": sources}
        )
        db.add(assistant_msg)
        db.commit()

        # 5. Audit
        self.audit.log_interaction(session.id, user.id, query, response_text, {"intent": intent})

        return {
            "response": response_text,
            "session_id": str(session.id),
            "intent": intent,
            "confidence": confidence,
            "sources": sources
        }

    async def _determine_intent_with_llm(self, db: Session, query: str, context: Optional[dict]) -> Dict[str, Any]:
        """
        Use LLM to determine intent.
        """
        try:
            prompt = PromptService.get_routing_prompt(query, context)
            # Use json_mode=True to enforce JSON output
            response_json_str, _ = await generate_completion(db, prompt, json_mode=True)
            
            # Parse JSON
            intent_data = json.loads(response_json_str)
            return intent_data
        except Exception as e:
            logger.error(f"Failed to determine intent with LLM: {e}")
            return {"intent": "general", "confidence": 0.5, "reasoning": "Fallback on error"}

    def _get_or_create_session(self, db: Session, session_id: Optional[str], user_id: UUID, context: Optional[dict]) -> AISession:
        # First, rollback any aborted transaction
        try:
            db.rollback()
        except Exception:
            pass
            
        if session_id:
            try:
                # Only try to parse as UUID if it looks like one
                if session_id.startswith("session-"):
                    # Extract the actual UUID part after "session-"
                    pass  # Not a UUID format, skip lookup
                else:
                    session = db.query(AISession).filter(AISession.id == session_id).first()
                    if session:
                        return session
            except Exception as e:
                logger.warning(f"Failed to fetch session {session_id}: {e}")
                db.rollback()  # Rollback on error
        
        try:
            session = AISession(
                user_id=user_id,
                title="New Conversation",
                context_context_json=context or {}
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            return session
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            db.rollback()
            # Return a mock session object to avoid breaking the flow
            from datetime import datetime
            class MockSession:
                id = None
                user_id = user_id
                title = "Temporary Session"
                context_context_json = context or {}
                created_at = datetime.utcnow()
                updated_at = datetime.utcnow()
            return MockSession()

_orchestrator = ReviveOrchestrator()

def get_revive_orchestrator():
    return _orchestrator
