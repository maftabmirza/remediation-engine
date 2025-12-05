"""
Ollama Service - Custom Ollama integration with Bearer token support
"""
import httpx
import json
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
from app.models import LLMProvider
from app.utils.crypto import decrypt_value

logger = logging.getLogger(__name__)


def get_ollama_api_key(provider: LLMProvider) -> Optional[str]:
    """Get decrypted API key for Ollama provider."""
    if provider.api_key_encrypted:
        return decrypt_value(provider.api_key_encrypted)
    return None


async def ollama_completion(
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 2000
) -> str:
    """
    Call Ollama API with Bearer token support.
    Returns the completion text.
    """
    if not provider.api_base_url:
        raise ValueError(f"No API base URL configured for provider: {provider.name}")
    
    api_key = get_ollama_api_key(provider)
    model_id = provider.model_id
    
    # Remove "ollama/" prefix if present
    if model_id.startswith("ollama/"):
        model_id = model_id.replace("ollama/", "")
    
    # Convert messages format if needed
    # Ollama /api/chat expects messages in a specific format
    prompt = messages[-1]["content"] if messages else ""
    
    headers = {
        "Content-Type": "application/json",
    }
    
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    payload = {
        "model": model_id,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Try /api/chat first (newer endpoint)
            url = f"{provider.api_base_url}/api/chat"
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "")
            elif response.status_code == 404:
                # Fall back to /api/generate (older endpoint)
                url = f"{provider.api_base_url}/api/generate"
                payload_gen = {
                    "model": model_id,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    }
                }
                response = await client.post(url, json=payload_gen, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "")
                else:
                    raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
            else:
                raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Ollama API call failed: {str(e)}")
        raise


async def ollama_completion_stream(
    provider: LLMProvider,
    messages: List[Dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 2000
) -> AsyncGenerator[str, None]:
    """
    Stream completions from Ollama API.
    """
    if not provider.api_base_url:
        raise ValueError(f"No API base URL configured for provider: {provider.name}")
    
    api_key = get_ollama_api_key(provider)
    model_id = provider.model_id
    
    # Remove "ollama/" prefix if present
    if model_id.startswith("ollama/"):
        model_id = model_id.replace("ollama/", "")
    
    headers = {
        "Content-Type": "application/json",
    }
    
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    payload = {
        "model": model_id,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            url = f"{provider.api_base_url}/api/chat"
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise Exception(f"Ollama API error: {response.status_code} - {error_text.decode()}")
                
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if "message" in data:
                                content = data["message"].get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        logger.error(f"Ollama streaming call failed: {str(e)}")
        raise
