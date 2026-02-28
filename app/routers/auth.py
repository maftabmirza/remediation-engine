"""
Authentication API endpoints.

Supports two auth flows:
  1. Local username/password  → POST /api/auth/login  (always available)
  2. CyberArk Identity SAML   → GET  /api/auth/saml/login        (SP-initiated)
                                 POST /api/auth/saml/acs          (assertion consumer)
                                 GET  /api/auth/saml/metadata     (SP metadata XML)

The SAML flow is dormant until an admin configures method="cyberark_saml" via
POST /api/auth/config.  Both flows issue identical JWTs so all downstream
authentication middleware is unchanged.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import RedirectResponse, Response as FastAPIResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, AuditLog
from app.schemas import LoginRequest, LoginResponse, UserResponse, UserCreate, ChangePasswordRequest
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    decode_token,
    blacklist_token,
    get_current_user,
    get_permissions_for_role,
    get_password_hash
)
from app.services.saml_service import (
    require_cyberark_config,
    is_cyberark_enabled,
    build_saml_auth,
    get_or_provision_sso_user,
    generate_sp_metadata,
)
from app.metrics import AUTH_ATTEMPTS
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
settings = get_settings()
limiter = Limiter(key_func=get_remote_address, enabled=not settings.testing)


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token.
    Also sets token as HTTP-only cookie for web UI.
    """
    user = authenticate_user(db, login_data.username, login_data.password)
    
    if not user:
        AUTH_ATTEMPTS.labels(status="failed").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        AUTH_ATTEMPTS.labels(status="disabled").inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Record successful login
    AUTH_ATTEMPTS.labels(status="success").inc()
    
    # Create token
    access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    
    # Log the login
    audit = AuditLog(
        user_id=user.id,
        action="login",
        resource_type="user",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    db.commit()
    
    # Set cookie for web UI
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=86400,  # 24 hours
        samesite="lax"
    )
    
    user_payload = UserResponse.model_validate(user)
    user_payload.permissions = list(get_permissions_for_role(db, user.role))

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_payload
    )


# ============================================================================ #
#  CyberArk Identity SAML 2.0 endpoints                                        #
# ============================================================================ #

@router.get("/saml/login")
async def saml_login(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    SP-initiated SAML login.
    Redirects the browser to CyberArk Identity for authentication.
    Returns 503 if CyberArk SSO is not configured.
    """
    cfg = require_cyberark_config(db)
    auth = await build_saml_auth(request, cfg)
    sso_url = auth.login()
    return RedirectResponse(url=sso_url, status_code=302)


@router.post("/saml/acs")
async def saml_acs(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Assertion Consumer Service (ACS) endpoint.
    CyberArk POSTs the SAML Response here after successful authentication.

    Flow:
      1. Validate SAML assertion (signature, conditions, timestamps)
      2. Extract NameID + user attributes
      3. Find / auto-provision local User
      4. Issue JWT + set HttpOnly cookie (identical to local login)
      5. Redirect to app root  (or return JSON for API clients)
    """
    cfg = require_cyberark_config(db)
    auth = await build_saml_auth(request, cfg)
    auth.process_response()

    errors = auth.get_errors()
    if errors:
        AUTH_ATTEMPTS.labels(status="sso_failed").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"CyberArk SAML authentication failed: {', '.join(errors)}",
        )

    if not auth.is_authenticated():
        AUTH_ATTEMPTS.labels(status="sso_failed").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="CyberArk SAML response was not authenticated.",
        )

    # ---- Extract attributes ----------------------------------------------- #
    sso_subject: str = auth.get_nameid() or ""
    attributes: dict = auth.get_attributes()

    attr_email    = cfg.get("attribute_email",    "email")
    attr_username = cfg.get("attribute_username", "username")
    attr_role     = cfg.get("attribute_role",     "role")

    def _first(attrs: dict, key: str) -> str:
        vals = attrs.get(key, [])
        return vals[0] if vals else ""

    email    = _first(attributes, attr_email)    or sso_subject
    username = _first(attributes, attr_username) or sso_subject.split("@")[0]
    cyberark_role_value = _first(attributes, attr_role)

    if not sso_subject:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CyberArk SAML response did not include a NameID.",
        )

    # ---- Find / provision user -------------------------------------------- #
    user, created = get_or_provision_sso_user(
        db=db,
        sso_subject=sso_subject,
        email=email,
        username=username,
        cyberark_role_value=cyberark_role_value,
        cfg=cfg,
        request=request,
    )

    if not user.is_active:
        AUTH_ATTEMPTS.labels(status="disabled").inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled.",
        )

    AUTH_ATTEMPTS.labels(status="sso_success").inc()

    # ---- Issue JWT (same as local login) ---------------------------------- #
    access_token = create_access_token(data={"sub": str(user.id), "username": user.username})

    user.last_login = datetime.now(timezone.utc)
    db.add(AuditLog(
        user_id=user.id,
        action="sso_login",
        resource_type="user",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
    ))
    db.commit()

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=86400,
        samesite="lax",
    )

    # Return JSON (API clients) and also a redirect header so browser UIs land on /
    user_payload = UserResponse.model_validate(user)
    user_payload.permissions = list(get_permissions_for_role(db, user.role))
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_payload,
    )


@router.get("/saml/metadata")
async def saml_metadata(
    db: Session = Depends(get_db),
):
    """
    Return the SP metadata XML.
    CyberArk administrators use this to register the app as a SAML Service Provider.
    This endpoint is public (no auth required) — standard SAML practice.
    """
    cfg = require_cyberark_config(db)
    xml = generate_sp_metadata(cfg)
    return FastAPIResponse(content=xml, media_type="application/xml")


@router.get("/saml/status")
async def saml_status(
    db: Session = Depends(get_db),
):
    """
    Quick health-check: is CyberArk SSO enabled?
    Returns the configured SP entity ID and ACS URL (no secrets).
    """
    cfg = require_cyberark_config(db) if is_cyberark_enabled(db) else None
    if not cfg:
        return {"enabled": False, "message": "CyberArk SSO is not configured."}
    return {
        "enabled": True,
        "sp_entity_id": cfg.get("sp_entity_id"),
        "sp_acs_url": cfg.get("sp_acs_url"),
        "auto_provision": cfg.get("auto_provision", True),
        "default_role": cfg.get("default_role", "viewer"),
        "login_url": "/api/auth/saml/login",
        "metadata_url": "/api/auth/saml/metadata",
    }


# ============================================================================ #
#  Original endpoints continue below                                            #
# ============================================================================ #

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/hour")
async def register(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Self-registration is disabled for security.
    Users must be created by an admin via the Settings > Users panel.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Self-registration is disabled. Contact an administrator to create an account."
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout user: clears the session cookie and revokes the current token
    so it cannot be replayed for the remainder of its validity window.
    """
    # Extract the raw token from cookie or Authorization header
    raw_token = request.cookies.get("access_token")
    if not raw_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            raw_token = auth_header[7:]

    # Revoke the token so it cannot be reused even before it expires
    if raw_token:
        payload = decode_token(raw_token)
        if payload:
            from datetime import datetime
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                blacklist_token(jti, datetime.utcfromtimestamp(exp))

    # Log the logout
    audit = AuditLog(
        user_id=current_user.id,
        action="logout",
        resource_type="user",
        resource_id=current_user.id,
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    db.commit()

    # Clear cookie
    response.delete_cookie(key="access_token")

    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user info.
    """
    payload = UserResponse.model_validate(current_user)
    payload.permissions = list(get_permissions_for_role(db, current_user.role))
    return payload


@router.post("/change-password")
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change current user's password.
    Requires current password for verification.
    """
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # Verify current password
    if not pwd_context.verify(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.password_hash = get_password_hash(password_data.new_password)
    db.commit()
    
    # Log the password change
    audit = AuditLog(
        user_id=current_user.id,
        action="change_password",
        resource_type="user",
        resource_id=current_user.id,
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    db.commit()
    
    return {"message": "Password changed successfully"}
