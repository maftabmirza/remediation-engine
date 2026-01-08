"""
Chat Service - LangChain integration
"""
from typing import List, Optional, AsyncGenerator
from uuid import UUID
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_community.chat_models import ChatLiteLLM
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from litellm import token_counter

from app.models import LLMProvider, Alert, AuditLog
from app.models_chat import ChatSession, ChatMessage
from app.services.llm_service import get_api_key_for_provider
from app.services.ollama_service import ollama_completion_stream
from app.services.ollama_service import ollama_completion_stream
from app.services.prompt_service import PromptService
from app.services.similarity_service import SimilarityService
from app.models_troubleshooting import AlertCorrelation
from app.services.runbook_search_service import RunbookSearchService
from app.services.solution_ranker import SolutionRanker
import json
import logging

logger = logging.getLogger(__name__)

async def get_chat_llm(provider: LLMProvider):
    """
    Get a LangChain Chat Model for the given provider.
    """
    import litellm  # Import to set API key directly
    
    api_key = get_api_key_for_provider(provider)
    
    # DEBUG: Log what key we're using
    key_preview = api_key[:20] if api_key else "NONE"
    logger.info(f"[DEBUG] get_chat_llm: provider={provider.name}, key_preview={key_preview}...")
    
    model_name = provider.model_id
    if provider.provider_type == "ollama" and not model_name.startswith("ollama/"):
        model_name = f"ollama/{model_name}"
    
    # FIX: Set API key directly on litellm module to override env var fallback
    # ChatLiteLLM ignores the api_key param, so we need to set it at module level
    if api_key:
        if provider.provider_type == "anthropic":
            litellm.anthropic_key = api_key
        elif provider.provider_type == "openai":
            litellm.openai_key = api_key
        elif provider.provider_type == "google":
            litellm.gemini_key = api_key
        # Generic fallback
        litellm.api_key = api_key
        
    # Configure LiteLLM via LangChain
    llm = ChatLiteLLM(
        model=model_name,
        api_key=api_key,
        api_base=provider.api_base_url,
        temperature=provider.config_json.get("temperature", 0.3),
        max_tokens=provider.config_json.get("max_tokens", 2000),
        streaming=True
    )
    
    return llm



async def stream_chat_response(
    db: Session,
    session_id: UUID,
    user_message: str,
    provider: LLMProvider
) -> AsyncGenerator[str, None]:
    """
    Stream the chat response from the LLM.
    """
    # 1. Save user message
    db_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=user_message
    )
    db.add(db_message)
    db.commit()
    
    # 2. Load history
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    
    # Audit log the user message
    audit_log = AuditLog(
        user_id=session.user_id,
        action="chat_message",
        resource_type="chat_session",
        resource_id=session_id,
        details_json={
            "content_snippet": user_message[:100] + "..." if len(user_message) > 100 else user_message,
            "alert_id": str(session.alert_id) if session.alert_id else None
        }
    )
    db.add(audit_log)
    db.commit()

    history_messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    # Convert to message format
    messages = []
    messages = []
    
    # Fetch Context
    alert = session.alert
    correlation = None
    similar_incidents = []
    
    if alert:
        if alert.correlation_id:
            correlation = db.query(AlertCorrelation).filter(AlertCorrelation.id == alert.correlation_id).first()
            
        # Try to find similar incidents
        try:
            sim_service = SimilarityService(db)
            sim_resp = sim_service.find_similar_alerts(alert.id, limit=3)
            if sim_resp:
                similar_incidents = [s.dict() for s in sim_resp.similar_incidents]
        except Exception as e:
            # Don't fail chat if similarity search fails
            pass

        similar_incidents = []
    
    if alert:
        if alert.correlation_id:
            correlation = db.query(AlertCorrelation).filter(AlertCorrelation.id == alert.correlation_id).first()
            
        # Try to find similar incidents
        try:
            sim_service = SimilarityService(db)
            sim_resp = sim_service.find_similar_alerts(alert.id, limit=3)
            if sim_resp:
                similar_incidents = [s.dict() for s in sim_resp.similar_incidents]
        except Exception as e:
            # Don't fail chat if similarity search fails
            pass

    # [NEW] Runbook Search & Visibility Logic
    runbook_results = []
    solutions_context = {}
    search_summary_footer = ""
    
    troubleshooting_keywords = [
        'high cpu', 'memory', 'disk', 'slow', 'error', 'fix', 'troubleshoot',
        'restart', 'down', 'failed', 'not working', 'issue', 'problem', 'crash',
        'latency', 'timeout', 'exception', 'bug', 'alert', 'incident',
        'search', 'find', 'lookup', 'how to', 'check', 'investigate', 'analyze', 'why', 'what is'
    ]
    
    is_troubleshooting = any(k in user_message.lower() for k in troubleshooting_keywords)
    print(f"DEBUG: is_troubleshooting={is_troubleshooting} for query='{user_message}'", flush=True)
    
    if is_troubleshooting:
        try:
            # 1. Search Runbooks
            rb_service = RunbookSearchService(db)
            ctx = {"os_type": "linux"} 
            
            runbook_results = await rb_service.search_runbooks(user_message, ctx, session.user, limit=3)
            logger.info(f"DEBUG: Runbook search found {len(runbook_results)} results")
            
            # 2. Rank Solutions
            if runbook_results:
                ranker = SolutionRanker(db)
                ranked = ranker.rank_and_combine_solutions(runbook_results, [], [], ctx)
                solutions_context = ranked.to_dict()
                
                count = len(solutions_context.get('solutions', []))
                logger.info(f"DEBUG: Ranker returned {count} solutions")
                
                # Filter to only high-confidence runbooks (>= 50%)
                filtered_solutions = [
                    s for s in solutions_context.get('solutions', []) 
                    if s.get('confidence', 0) >= 0.5
                ]
                solutions_context['solutions'] = filtered_solutions
                logger.info(f"DEBUG: After filtering: {len(filtered_solutions)} solutions above 50% confidence")
                
                # Build footer with runbook links (always shown)
                footer_parts = ["\n\n---\n\n**📚 Related Runbooks:**\n"]
                for sol in solutions_context.get('solutions', []):
                    title = sol.get('title', 'Untitled')
                    url = sol.get('metadata', {}).get('url', '#')
                    confidence = sol.get('confidence', 0)
                    
                    # Convert confidence to visual indicator
                    if confidence >= 0.7:
                        indicator = "⭐⭐⭐"
                    elif confidence >= 0.5:
                        indicator = "⭐⭐"
                    else:
                        indicator = "⭐"
                    
                    footer_parts.append(f"- **[{title}]({url})** {indicator} ({confidence:.0%} match)")
                
                search_summary_footer = "\n".join(footer_parts)
                logger.info(f"DEBUG: Built footer with {count} runbook links")
                
            else:
                logger.info("DEBUG: No runbooks found for query")
                    
        except Exception as e:
            logger.error(f"Error in ChatService runbook search: {e}", exc_info=True)

    # Pass ranked_solutions to PromptService (it will format instructions)
    system_prompt = PromptService.get_system_prompt(
        alert=alert, 
        correlation=correlation, 
        similar_incidents=similar_incidents,
        ranked_solutions=solutions_context  # NEW: Let PromptService handle formatting instructions
    )
    
    
    # [MODIFIED] Merge Runbook Context into System Prompt
    runbook_system_part = ""
    if solutions_context and solutions_context.get('solutions'):
        runbook_snippets = []
        for sol in solutions_context['solutions']:
            title = sol.get('title', 'Untitled Runbook')
            desc = sol.get('description', '')
            confidence = sol.get('confidence', 0)
            permission = sol.get('permission_status', 'unknown')
            url = sol.get('metadata', {}).get('url', '/remediation/runbooks')
            
            # Convert confidence to stars
            if confidence >= 0.9: stars = "⭐⭐⭐⭐⭐"
            elif confidence >= 0.8: stars = "⭐⭐⭐⭐"
            elif confidence >= 0.7: stars = "⭐⭐⭐"
            elif confidence >= 0.5: stars = "⭐⭐"
            else: stars = "⭐"
            
            # Format permission
            perm_text = "✅ You can execute" if permission == "can_execute" else "🔒 View only"
            
            snippet = f"""**[Runbook: {title}]({url})**
Confidence: {stars} ({confidence:.0%}) | Permission: {perm_text}

{desc}"""
            runbook_snippets.append(snippet)
        
        # Inject as available context
        runbook_context = "\n\n---\n\n".join(runbook_snippets)
        logger.info(f"DEBUG: Injecting {len(runbook_snippets)} runbooks into context")

    # Use base system prompt only (keep it clean)
    messages.append({"role": "system", "content": system_prompt})
    
    # Add history (excluding the last user message which we'll enhance)
    for msg in history_messages[:-1] if history_messages else []:
        messages.append({"role": msg.role, "content": msg.content})
    
    # Enhance the user message with runbook context (positions it for maximum attention)
    if solutions_context and solutions_context.get('solutions'):
        enhanced_user_message = f"""[CONTEXT FROM KNOWLEDGE BASE]
Our documentation has the following relevant runbooks for this query:

{runbook_context}

When a runbook directly addresses my question, please reference it with its link.

[USER QUESTION]
{user_message}"""
        messages.append({"role": "user", "content": enhanced_user_message})
    else:
        messages.append({"role": "user", "content": user_message})
            
    # Stream response
    full_response = ""
    
    if provider.provider_type == "ollama":
        # Use custom Ollama streaming
        config = provider.config_json or {}
        temperature = config.get("temperature", 0.3)
        max_tokens = config.get("max_tokens", 2000)
        
        async for chunk in ollama_completion_stream(
            provider=provider,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            full_response += chunk
            yield chunk
    else:
        # Use LangChain with LiteLLM for other providers
        # Convert our messages list to LangChain format
        lc_messages = []
        for msg in messages:
            if msg['role'] == 'system':
                lc_messages.append(SystemMessage(content=msg['content']))
            elif msg['role'] == 'user':
                lc_messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                lc_messages.append(AIMessage(content=msg['content']))
                
        llm = await get_chat_llm(provider)
        
        async for chunk in llm.astream(lc_messages):
            content = chunk.content
            if content:
                full_response += content
                yield content
    
    
    # Append runbook footer if available (guarantees visibility)
    if search_summary_footer:
        full_response += search_summary_footer
        yield search_summary_footer

    # Save assistant message (with footer)
    tokens = 0
    try:
        tokens = token_counter(model=provider.model_id, messages=messages)
    except:
        pass

    ai_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=full_response,
        tokens_used=tokens
    )
    db.add(ai_message)
    db.commit()

