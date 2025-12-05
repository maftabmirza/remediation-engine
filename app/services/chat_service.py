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

async def get_chat_llm(provider: LLMProvider):
    """
    Get a LangChain Chat Model for the given provider.
    """
    api_key = get_api_key_for_provider(provider)
    
    model_name = provider.model_id
    if provider.provider_type == "ollama" and not model_name.startswith("ollama/"):
        model_name = f"ollama/{model_name}"
        
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

def get_system_prompt(alert: Optional[Alert] = None) -> str:
    """
    Generate the system prompt for the chat.
    """
    base_prompt = """You are an expert Site Reliability Engineer (SRE) assistant.
Your goal is to help the user troubleshoot and resolve infrastructure alerts.

GUIDELINES:
1. Be concise and direct.
2. When suggesting commands, ALWAYS wrap them in markdown code blocks with the language specified (e.g., ```bash).
3. If you suggest a remediation, explain the risks first.
4. You can ask clarifying questions if the alert details are insufficient.
5. The user may provide TERMINAL OUTPUT in their message. Use this output to analyze the situation.
"""

    if alert:
        alert_context = f"""
CURRENT ALERT CONTEXT:
- Name: {alert.alert_name}
- Severity: {alert.severity}
- Instance: {alert.instance}
- Status: {alert.status}
- Summary: {alert.annotations_json.get('summary', 'N/A')}
- Description: {alert.annotations_json.get('description', 'N/A')}
"""
        return base_prompt + alert_context
    
    return base_prompt

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
    system_prompt = get_system_prompt(session.alert)
    messages.append({"role": "system", "content": system_prompt})
    
    for msg in history_messages:
        messages.append({"role": msg.role, "content": msg.content})
            
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
        lc_messages = []
        lc_messages.append(SystemMessage(content=system_prompt))
        
        for msg in history_messages:
            if msg.role == "user":
                lc_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                lc_messages.append(AIMessage(content=msg.content))
                
        llm = await get_chat_llm(provider)
        
        async for chunk in llm.astream(lc_messages):
            content = chunk.content
            if content:
                full_response += content
                yield content
            
    # Save assistant message
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

