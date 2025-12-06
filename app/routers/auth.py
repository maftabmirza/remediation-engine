"""
Authentication API endpoints
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, AuditLog
from app.schemas import LoginRequest, LoginResponse, UserResponse
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    get_current_user,
    get_permissions_for_role
)
from app.metrics import AUTH_ATTEMPTS
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)


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
    user_payload.permissions = list(get_permissions_for_role(user.role))

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_payload
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout user by clearing the cookie.
    """
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
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user info.
    """
    payload = UserResponse.model_validate(current_user)
    payload.permissions = list(get_permissions_for_role(current_user.role))
    return payload
