"""
Settings API endpoints - LLM Providers management
"""
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LLMProvider, User, AuditLog
from app.schemas import (
    LLMProviderCreate, LLMProviderUpdate, LLMProviderResponse
)
from app.services.auth_service import get_current_user, require_admin
from app.utils.crypto import encrypt_value
from app.services.llm_service import get_api_key_for_provider
from litellm import completion

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("/llm/{provider_id}/test")
async def test_llm_provider(
    provider_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Test if an LLM provider is working"""
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    try:
        api_key = get_api_key_for_provider(provider)
        
        # Prepare model name for LiteLLM
        model_name = provider.model_id
        if provider.provider_type == "ollama" and not model_name.startswith("ollama/"):
            model_name = f"ollama/{model_name}"
            
        kwargs = {
            "model": model_name,
            "messages": [{"role": "user", "content": "Say OK"}],
            "max_tokens": 10,
        }
        
        # Handle authentication based on provider type
        if provider.provider_type == "ollama":
            # Ollama with API key (Bearer token)
            if api_key:
                kwargs["api_key"] = api_key
        else:
            # Other providers
            if api_key:
                kwargs["api_key"] = api_key
            
        if provider.api_base_url:
            kwargs["api_base"] = provider.api_base_url
            
        response = completion(**kwargs)
        return {"status": "success", "response": response.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/llm", response_model=List[LLMProviderResponse])
async def list_llm_providers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all LLM providers.
    """
    providers = db.query(LLMProvider).all()
    
    # Convert to response model with has_api_key flag
    result = []
    for p in providers:
        response = LLMProviderResponse.model_validate(p)
        response.has_api_key = bool(p.api_key_encrypted)
        if p.config_json and p.config_json.get("secret_last_rotated"):
            response.secret_last_rotated = p.config_json.get("secret_last_rotated")
        result.append(response)
    
    return result


@router.post("/llm", response_model=LLMProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_llm_provider(
    request: Request,
    provider_data: LLMProviderCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new LLM provider. Admin only.
    """
    # Validate provider type
    valid_types = ["anthropic", "openai", "google", "ollama", "azure"]
    if provider_data.provider_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider type must be one of: {', '.join(valid_types)}"
        )

    requires_secret = provider_data.provider_type != "ollama"
    if requires_secret and not provider_data.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is required for hosted providers"
        )

    # Prepare config with sane defaults
    config = provider_data.config_json or {}
    config.setdefault("secret_storage", "vault")
    
    # If setting as default, unset other defaults
    if provider_data.is_default:
        db.query(LLMProvider).update({LLMProvider.is_default: False})
    
    rotation_time = None
    if provider_data.api_key:
        rotation_time = provider_data.config_json.get("secret_last_rotated") if provider_data.config_json else None
        rotation_time = rotation_time or datetime.utcnow()
        config["secret_last_rotated"] = rotation_time.isoformat()

    provider = LLMProvider(
        name=provider_data.name,
        provider_type=provider_data.provider_type,
        model_id=provider_data.model_id,
        api_key_encrypted=encrypt_value(provider_data.api_key),
        api_base_url=provider_data.api_base_url,
        is_default=provider_data.is_default,
        is_enabled=provider_data.is_enabled,
        config_json=config
    )
    
    db.add(provider)
    db.commit()
    db.refresh(provider)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="create_llm_provider",
        resource_type="llm_provider",
        resource_id=provider.id,
        details_json={
            "name": provider.name,
            "provider_type": provider.provider_type,
            "secret_rotated_at": rotation_time.isoformat() if rotation_time else None,
        },
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    db.commit()

    response = LLMProviderResponse.model_validate(provider)
    response.has_api_key = bool(provider.api_key_encrypted)
    if provider.config_json and provider.config_json.get("secret_last_rotated"):
        response.secret_last_rotated = provider.config_json.get("secret_last_rotated")
    return response


@router.get("/llm/{provider_id}", response_model=LLMProviderResponse)
async def get_llm_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific LLM provider.
    """
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM provider not found"
        )

    response = LLMProviderResponse.model_validate(provider)
    response.has_api_key = bool(provider.api_key_encrypted)
    if provider.config_json and provider.config_json.get("secret_last_rotated"):
        response.secret_last_rotated = provider.config_json.get("secret_last_rotated")
    return response


@router.put("/llm/{provider_id}", response_model=LLMProviderResponse)
async def update_llm_provider(
    provider_id: UUID,
    request: Request,
    provider_data: LLMProviderUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update an LLM provider. Admin only.
    """
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM provider not found"
        )

    update_data = provider_data.model_dump(exclude_unset=True)

    # If setting as default, unset other defaults
    if update_data.get("is_default"):
        db.query(LLMProvider).filter(LLMProvider.id != provider_id).update({LLMProvider.is_default: False})

    # Handle API key separately (rename field)
    if "api_key" in update_data:
        update_data["api_key_encrypted"] = encrypt_value(update_data.pop("api_key"))
        if update_data["api_key_encrypted"]:
            # Stamp rotation time in config
            config = update_data.get("config_json", provider.config_json or {}) or {}
            config["secret_last_rotated"] = datetime.utcnow().isoformat()
            update_data["config_json"] = config

    for field, value in update_data.items():
        setattr(provider, field, value)

    requires_secret = provider.provider_type != "ollama"
    if requires_secret and not provider.api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is required for hosted providers"
        )

    # Normalize config defaults
    provider.config_json = (provider.config_json or {})
    provider.config_json.setdefault("secret_storage", "vault")

    db.commit()
    db.refresh(provider)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="update_llm_provider",
        resource_type="llm_provider",
        resource_id=provider.id,
        details_json={"updated_fields": list(update_data.keys())},
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    db.commit()

    response = LLMProviderResponse.model_validate(provider)
    response.has_api_key = bool(provider.api_key_encrypted)
    if provider.config_json and provider.config_json.get("secret_last_rotated"):
        response.secret_last_rotated = provider.config_json.get("secret_last_rotated")
    return response


@router.delete("/llm/{provider_id}")
async def delete_llm_provider(
    provider_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete an LLM provider. Admin only.
    """
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM provider not found"
        )
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="delete_llm_provider",
        resource_type="llm_provider",
        resource_id=provider.id,
        details_json={"name": provider.name},
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    
    db.delete(provider)
    db.commit()
    
    return {"message": "LLM provider deleted successfully"}


@router.post("/llm/{provider_id}/set-default")
async def set_default_provider(
    provider_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Set an LLM provider as default. Admin only.
    """
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM provider not found"
        )
    
    if not provider.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set disabled provider as default"
        )
    
    # Unset all defaults
    db.query(LLMProvider).update({LLMProvider.is_default: False})
    
    # Set this one as default
    provider.is_default = True
    db.commit()
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="set_default_llm_provider",
        resource_type="llm_provider",
        resource_id=provider.id,
        details_json={"name": provider.name},
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    db.commit()
    
    return {"message": f"{provider.name} set as default provider"}


@router.post("/llm/{provider_id}/toggle")
async def toggle_provider(
    provider_id: UUID,
    request: Request,
    enabled: Optional[bool] = Query(default=None, description="Force enabled state if provided"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Toggle an LLM provider's enabled status. Admin only.
    """
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="LLM provider not found"
        )
    
    provider.is_enabled = enabled if enabled is not None else not provider.is_enabled
    
    # If disabling the default, unset default
    if not provider.is_enabled and provider.is_default:
        provider.is_default = False
    
    db.commit()
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="toggle_llm_provider",
        resource_type="llm_provider",
        resource_id=provider.id,
        details_json={"name": provider.name, "enabled": provider.is_enabled},
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    db.commit()
    
    return {"message": f"Provider {'enabled' if provider.is_enabled else 'disabled'}", "enabled": provider.is_enabled}
