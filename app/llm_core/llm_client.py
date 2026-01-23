"""
LLM Client Wrapper - Centralized LLM Interaction
"""
import time
import logging
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from litellm import acompletion
from app.models import LLMProvider
from app.llm_core.provider_selection import get_api_key_for_provider, get_default_provider, get_json_mode_support
from app.services.ollama_service import ollama_completion
from app.metrics import LLM_REQUESTS, LLM_DURATION

logger = logging.getLogger(__name__)

async def call_llm(
    db: Session,
    prompt: str,
    system_prompt: Optional[str] = None,
    provider: Optional[LLMProvider] = None,
    json_mode: bool = False,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> Tuple[str, LLMProvider]:
    """
    Unified method to call LLM providers.
    """
    if not provider:
        provider = get_default_provider(db)
        if not provider:
            # Fallback to any enabled provider
            provider = db.query(LLMProvider).filter(LLMProvider.is_enabled == True).first()
    
    if not provider:
        raise ValueError("No LLM provider configured or enabled")
    
    api_key = get_api_key_for_provider(provider)
    if not api_key and provider.provider_type not in ["ollama"]:
        raise ValueError(f"No API key configured for provider: {provider.name}")
    
    config = provider.config_json or {}
    temperature = temperature if temperature is not None else config.get("temperature", 0.3)
    max_tokens = max_tokens if max_tokens is not None else config.get("max_tokens", 2000)
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    start_time = time.time()
    try:
        logger.info(f"Calling LLM: {provider.name} ({provider.provider_type})")
        
        if provider.provider_type == "ollama":
            content = await ollama_completion(
                provider=provider,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            kwargs = {
                "model": provider.model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            if json_mode and get_json_mode_support(provider):
                 kwargs["response_format"] = { "type": "json_object" }
            
            if api_key:
                kwargs["api_key"] = api_key
            if provider.api_base_url:
                kwargs["api_base"] = provider.api_base_url
                
            response = await acompletion(**kwargs)
            content = response.choices[0].message.content
            
        duration = time.time() - start_time
        LLM_REQUESTS.labels(provider=provider.provider_type, model=provider.model_id, status="success").inc()
        LLM_DURATION.labels(provider=provider.provider_type, model=provider.model_id).observe(duration)
        
        return content, provider
        
    except Exception as e:
        duration = time.time() - start_time
        LLM_REQUESTS.labels(provider=provider.provider_type, model=provider.model_id, status="error").inc()
        LLM_DURATION.labels(provider=provider.provider_type, model=provider.model_id).observe(duration)
        logger.error(f"LLM call failed: {e}")
        raise RuntimeError(f"LLM API call failed: {str(e)}")
