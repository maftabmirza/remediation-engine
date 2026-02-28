"""
CyberArk Identity SAML 2.0 SSO service.

This module is intentionally dormant when auth_method != "cyberark_saml".
All functions check the active auth config before doing anything, so local
login is completely unaffected until an admin explicitly switches the method.

Integration overview
---------------------
1. Admin stores CyberArk config via  POST /api/auth/config  (method="cyberark_saml")
2. User hits GET  /api/auth/saml/login  → redirected to CyberArk Identity portal
3. CyberArk authenticates the user, POSTs SAML assertion to ACS
4. POST /api/auth/saml/acs  validates assertion, finds/creates the local User,
   issues the standard JWT + cookie — all downstream auth stays unchanged.

python3-saml library docs: https://github.com/onelogin/python3-saml
"""
from __future__ import annotations

import secrets
import string
from typing import Optional, Dict, Any, Tuple

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models import User, SystemConfig, AuditLog
from app.services.auth_service import (
    create_access_token,
    get_password_hash,
    normalize_role,
    VALID_ROLES,
    DEFAULT_ROLE,
)


# --------------------------------------------------------------------------- #
#  Config helpers                                                               #
# --------------------------------------------------------------------------- #

def get_cyberark_config(db: Session) -> Optional[Dict[str, Any]]:
    """Return cyberark_config dict from SystemConfig, or None if not configured."""
    row = db.query(SystemConfig).filter(SystemConfig.key == "auth_config").first()
    if not row:
        return None
    cfg = row.value_json or {}
    if cfg.get("method") != "cyberark_saml":
        return None
    return cfg.get("cyberark_config") or None


def require_cyberark_config(db: Session) -> Dict[str, Any]:
    """Return cyberark_config or raise 503 if SSO is not configured."""
    cfg = get_cyberark_config(db)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CyberArk SSO is not configured. Contact your administrator.",
        )
    return cfg


def is_cyberark_enabled(db: Session) -> bool:
    """Quick check — is cyberark_saml the active auth method?"""
    return get_cyberark_config(db) is not None


# --------------------------------------------------------------------------- #
#  SP settings builder for python3-saml                                        #
# --------------------------------------------------------------------------- #

def build_saml_settings(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the settings dict expected by python3-saml's OneLogin_Saml2_Auth.

    cfg keys used:
      idp_metadata_url   | idp_metadata_xml  (one is required)
      sp_entity_id
      sp_acs_url
    """
    # IdP descriptor: we inline it from XML when an URL is not available yet
    idp_metadata_xml: str = cfg.get("idp_metadata_xml", "")
    idp_metadata_url: str = cfg.get("idp_metadata_url", "")

    # Parse IdP fields from metadata XML if present
    idp_section: Dict[str, Any] = {}
    if idp_metadata_xml:
        try:
            from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser
            parsed = OneLogin_Saml2_IdPMetadataParser.parse(idp_metadata_xml)
            idp_section = parsed.get("idp", {})
        except Exception as exc:  # pragma: no cover
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to parse CyberArk IdP metadata: {exc}",
            )
    elif idp_metadata_url:
        try:
            from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser
            parsed = OneLogin_Saml2_IdPMetadataParser.parse_remote(idp_metadata_url)
            idp_section = parsed.get("idp", {})
        except Exception as exc:  # pragma: no cover
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch CyberArk IdP metadata from URL: {exc}",
            )

    return {
        "strict": True,
        "debug": False,
        "sp": {
            "entityId": cfg["sp_entity_id"],
            "assertionConsumerService": {
                "url": cfg["sp_acs_url"],
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": "",
            "privateKey": "",
        },
        "idp": idp_section,
        "security": {
            "nameIdEncrypted": False,
            "authnRequestsSigned": False,
            "logoutRequestSigned": False,
            "logoutResponseSigned": False,
            "signMetadata": False,
            "wantMessagesSigned": False,
            "wantAssertionsSigned": True,
            "wantNameId": True,
            "wantNameIdEncrypted": False,
            "wantAssertionsEncrypted": False,
            "allowSingleLabelDomains": False,
            "signatureAlgorithm": "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256",
            "digestAlgorithm": "http://www.w3.org/2001/04/xmlenc#sha256",
        },
    }


async def build_saml_auth(request: Request, cfg: Dict[str, Any]):
    """
    Construct a python3-saml OneLogin_Saml2_Auth instance from the incoming request.
    Raises ImportError with a friendly message if python3-saml is not installed.
    """
    try:
        from onelogin.saml2.auth import OneLogin_Saml2_Auth
        from onelogin.saml2.utils import OneLogin_Saml2_Utils
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "python3-saml is required for CyberArk SSO but is not installed. "
                "Add 'python3-saml>=1.16.0' to requirements.txt and rebuild the image."
            ),
        ) from exc

    body = await request.body()
    form_data: Dict[str, Any] = {}
    if body:
        from urllib.parse import parse_qs
        parsed = parse_qs(body.decode("utf-8"))
        form_data = {k: v[0] for k, v in parsed.items()}

    req = {
        "https": "on" if request.url.scheme == "https" else "off",
        "http_host": request.url.hostname,
        "server_port": str(request.url.port or (443 if request.url.scheme == "https" else 80)),
        "script_name": request.url.path,
        "get_data": dict(request.query_params),
        "post_data": form_data,
    }

    saml_settings = build_saml_settings(cfg)
    return OneLogin_Saml2_Auth(req, saml_settings)


# --------------------------------------------------------------------------- #
#  User provisioning                                                            #
# --------------------------------------------------------------------------- #

def _random_unusable_password() -> str:
    """Generate a random password hash string that can never be entered by a user."""
    chars = string.ascii_letters + string.digits
    return get_password_hash("!SSO!" + "".join(secrets.choice(chars) for _ in range(40)))


def map_cyberark_role(cyberark_role_value: str, cfg: Dict[str, Any]) -> str:
    """
    Map a CyberArk group/role name to an app role using the role_mapping config.
    Falls back to default_role (default: viewer) if no mapping matches.
    """
    role_mapping: Dict[str, str] = cfg.get("role_mapping") or {}
    default_role: str = cfg.get("default_role") or "viewer"

    # role_value may be a comma-separated list of groups or a single value
    groups = [g.strip() for g in cyberark_role_value.split(",") if g.strip()]

    # Priority order: match the highest-privilege role found
    priority = ["owner", "admin", "security_admin", "maintainer", "operator", "security_viewer", "auditor", "viewer"]

    matched_roles = []
    for group in groups:
        role = role_mapping.get(group)
        if role:
            matched_roles.append(normalize_role(role))

    # Pick highest-privilege matched role
    for p in priority:
        if p in matched_roles:
            return p

    normalized_default = normalize_role(default_role)
    return normalized_default if normalized_default in VALID_ROLES else DEFAULT_ROLE


def get_or_provision_sso_user(
    db: Session,
    sso_subject: str,
    email: str,
    username: str,
    cyberark_role_value: str,
    cfg: Dict[str, Any],
    request: Request,
) -> Tuple[User, bool]:
    """
    Find an existing user by sso_subject, fall back to email match, or create a new one.

    Returns (user, created_flag).
    """
    # 1. Try exact sso_subject match (fastest path after first login)
    user: Optional[User] = db.query(User).filter(User.sso_subject == sso_subject).first()

    # 2. Fall back to email (handles users that pre-existed before SSO was enabled)
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Link the existing local account to the CyberArk subject
            user.sso_subject = sso_subject
            user.auth_provider = "cyberark"

    created = False
    if not user:
        # 3. Auto-provision a new user
        auto_provision: bool = cfg.get("auto_provision", True)
        if not auto_provision:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"User '{username or email}' authenticated via CyberArk but does not "
                    "have a local account. Auto-provisioning is disabled."
                ),
            )

        app_role = map_cyberark_role(cyberark_role_value, cfg)

        # Derive a safe username
        safe_username = (username or email.split("@")[0]).replace(" ", "_").lower()[:50]
        # Ensure uniqueness
        base = safe_username
        suffix = 1
        while db.query(User).filter(User.username == safe_username).first():
            safe_username = f"{base}{suffix}"
            suffix += 1

        user = User(
            username=safe_username,
            email=email or None,
            full_name=username or None,
            password_hash=_random_unusable_password(),  # unusable — login only via SSO
            role=app_role,
            is_active=True,
            sso_subject=sso_subject,
            auth_provider="cyberark",
        )
        db.add(user)
        db.flush()  # get user.id before commit
        created = True

        # Audit
        db.add(AuditLog(
            user_id=user.id,
            action="sso_user_provisioned",
            resource_type="user",
            resource_id=user.id,
            ip_address=request.client.host if request.client else None,
        ))
    else:
        # Update role from CyberArk on every login (keeps in sync with IdP groups)
        app_role = map_cyberark_role(cyberark_role_value, cfg)
        if user.role != app_role:
            user.role = app_role
        user.auth_provider = "cyberark"

    return user, created


# --------------------------------------------------------------------------- #
#  SP Metadata XML generator                                                    #
# --------------------------------------------------------------------------- #

def generate_sp_metadata(cfg: Dict[str, Any]) -> str:
    """Return the SP metadata XML string for this application."""
    try:
        from onelogin.saml2.settings import OneLogin_Saml2_Settings
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="python3-saml is not installed.",
        ) from exc

    saml_settings_dict = build_saml_settings(cfg)
    # For metadata we don't need full IdP data, patch with empty if not loaded yet
    if not saml_settings_dict["idp"]:
        saml_settings_dict["idp"] = {
            "entityId": "placeholder",
            "singleSignOnService": {"url": "placeholder", "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"},
            "x509cert": "",
        }
    settings = OneLogin_Saml2_Settings(settings=saml_settings_dict, sp_validation_only=True)
    metadata = settings.get_sp_metadata()
    errors = settings.validate_metadata(metadata)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SP metadata validation errors: {errors}",
        )
    return metadata
