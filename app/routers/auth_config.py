"""
Authentication Configuration API
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import SystemConfig, User
from app.services.auth_service import require_admin

router = APIRouter(prefix="/api/auth/config", tags=["Auth Config"])

class AuthConfig(BaseModel):
    method: str  # "local", "ldap", "saml"
    ldap_config: Optional[Dict[str, Any]] = None
    saml_config: Optional[Dict[str, Any]] = None

@router.get("", response_model=AuthConfig)
async def get_auth_config(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get current authentication configuration"""
    config = db.query(SystemConfig).filter(SystemConfig.key == "auth_config").first()
    if not config:
        return AuthConfig(method="local")
    
    try:
        return AuthConfig(**config.value_json)
    except Exception:
        # Fallback if config is corrupted or schema changed
        return AuthConfig(method="local")

@router.post("", response_model=AuthConfig)
async def update_auth_config(
    data: AuthConfig,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update authentication configuration"""
    config = db.query(SystemConfig).filter(SystemConfig.key == "auth_config").first()
    if not config:
        config = SystemConfig(key="auth_config", value_json=data.model_dump())
        db.add(config)
    else:
        config.value_json = data.model_dump()
    
    db.commit()
    db.refresh(config)
    return AuthConfig(**config.value_json)
