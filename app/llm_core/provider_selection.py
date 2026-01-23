"""
LLM Provider Selection and Validation Logic
"""
import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models import LLMProvider
from app.config import get_settings
from app.utils.crypto import decrypt_value

logger = logging.getLogger(__name__)
settings = get_settings()

def get_api_key_for_provider(provider: LLMProvider) -> Optional[str]:
    """Get API key for a provider."""
    if provider.api_key_encrypted:
        return decrypt_value(provider.api_key_encrypted)
    
    if provider.provider_type == "anthropic":
        return settings.anthropic_api_key
    elif provider.provider_type == "openai":
        return settings.openai_api_key
    elif provider.provider_type == "google":
        return settings.google_api_key
    
    return None

def get_default_provider(db: Session) -> Optional[LLMProvider]:
    """Get the default LLM provider."""
    return db.query(LLMProvider).filter(
        LLMProvider.is_default == True,
        LLMProvider.is_enabled == True
    ).first()

def get_available_providers(db: Session) -> List[LLMProvider]:
    """Get all enabled LLM providers."""
    return db.query(LLMProvider).filter(
        LLMProvider.is_enabled == True
    ).all()

def validate_provider(provider: LLMProvider) -> bool:
    """Validate if provider has necessary configuration."""
    if provider.provider_type == "ollama":
        return True
    
    api_key = get_api_key_for_provider(provider)
    return api_key is not None

def get_json_mode_support(provider: LLMProvider) -> bool:
    """Check if provider supports JSON mode."""
    # Anthropic doesn't support response_format parameter in LiteLLM comfortably yet
    if provider.provider_type == "anthropic":
        return False
    return True
