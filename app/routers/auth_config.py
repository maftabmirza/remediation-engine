"""
Authentication Configuration API
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, model_validator

from app.database import get_db
from app.models import SystemConfig, User
from app.services.auth_service import require_admin

router = APIRouter(prefix="/api/auth/config", tags=["Auth Config"])

class AuthConfig(BaseModel):
    method: str  # "local", "ldap", "saml", "cyberark_saml"
    ldap_config: Optional[Dict[str, Any]] = None
    saml_config: Optional[Dict[str, Any]] = None
    cyberark_config: Optional[Dict[str, Any]] = None
    """
    cyberark_config expected keys:
      - idp_metadata_url  : CyberArk Identity IdP metadata URL (or leave blank, upload xml)
      - idp_metadata_xml  : Raw IdP metadata XML string (alternative to URL)
      - sp_entity_id      : e.g. https://your-app/api/auth/saml/metadata
      - sp_acs_url        : e.g. https://your-app/api/auth/saml/acs
      - attribute_email   : SAML attribute name carrying the email  (default: email)
      - attribute_username: SAML attribute name carrying the username (default: username)
      - attribute_role    : SAML attribute name carrying the role/group (default: role)
      - role_mapping      : dict mapping CyberArk group names -> app roles
                            e.g. {"CyberArk_Admins": "admin", "CyberArk_Ops": "operator"}
      - auto_provision    : bool – create user on first SSO login (default: true)
      - default_role      : role assigned when no role_mapping match (default: "viewer")
    """

    @model_validator(mode="after")
    def validate_method_requirements(self):
        if self.method == "ldap":
            if not self.ldap_config or not all(self.ldap_config.get(k) for k in ["url", "bind_dn", "base_dn"]):
                raise HTTPException(status_code=400, detail="LDAP configuration requires url, bind_dn, and base_dn")
        if self.method == "saml":
            if not self.saml_config or not all(self.saml_config.get(k) for k in ["metadata_url", "entity_id"]):
                raise HTTPException(status_code=400, detail="SAML configuration requires metadata_url and entity_id")
        if self.method == "cyberark_saml":
            if not self.cyberark_config:
                raise HTTPException(status_code=400, detail="cyberark_config is required for cyberark_saml method")
            required = ["sp_entity_id", "sp_acs_url"]
            missing = [k for k in required if not self.cyberark_config.get(k)]
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"cyberark_config missing required fields: {', '.join(missing)}"
                )
            has_metadata = self.cyberark_config.get("idp_metadata_url") or self.cyberark_config.get("idp_metadata_xml")
            if not has_metadata:
                raise HTTPException(
                    status_code=400,
                    detail="cyberark_config requires either idp_metadata_url or idp_metadata_xml"
                )
        if self.method not in {"local", "ldap", "saml", "cyberark_saml"}:
            raise HTTPException(status_code=400, detail="Authentication method must be local, ldap, saml, or cyberark_saml")
        return self

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
        config = SystemConfig(
            key="auth_config",
            value_json=data.model_dump(),
            updated_by=current_user.id
        )
        db.add(config)
    else:
        config.value_json = data.model_dump()
        config.updated_by = current_user.id

    db.commit()
    db.refresh(config)
    return AuthConfig(**config.value_json)


@router.post("/test", response_model=dict)
async def test_auth_flow(
    data: AuthConfig,
    current_user: User = Depends(require_admin),
):
    """Lightweight validation endpoint to dry-run LDAP/SAML config."""
    # The AuthConfig validator will enforce required fields per method.
    # Here we simply echo readiness since external IdP testing is not possible offline.
    readiness = {
        "method": data.method,
        "ready": True,
        "message": "Configuration is syntactically valid; complete provider-side checks to finish.",
    }
    return readiness
