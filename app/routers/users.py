"""
User Management API endpoints
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import User, AuditLog, Alert, AutoAnalyzeRule, ServerCredential, SystemConfig, TerminalSession
from app.models_chat import ChatSession
from app.services.auth_service import (
    get_current_user, 
    require_admin, 
    get_password_hash,
    get_user_by_username
)

router = APIRouter(prefix="/api/users", tags=["Users"])

class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: str
    role: str = "user"
    is_active: bool = True

class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id: UUID
    username: str
    email: Optional[str]
    full_name: Optional[str]
    role: str
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all users (Admin only)"""
    return db.query(User).all()

@router.post("", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new user (Admin only)"""
    if get_user_by_username(db, data.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    
    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        password_hash=get_password_hash(data.password),
        role=data.role,
        is_active=data.is_active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action="create_user",
        resource_type="user",
        resource_id=user.id,
        details_json={"username": user.username, "role": user.role}
    )
    db.add(audit)
    db.commit()
    
    return user

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a user (Admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if data.password:
        user.password_hash = get_password_hash(data.password)
    if data.role:
        user.role = data.role
    if data.email is not None:
        user.email = data.email
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.is_active is not None:
        user.is_active = data.is_active
        
    db.commit()
    db.refresh(user)
    
    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action="update_user",
        resource_type="user",
        resource_id=user.id,
        details_json={"changes": data.model_dump(exclude_unset=True)}
    )
    db.add(audit)
    db.commit()
    
    return user

@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Soft delete a user (Admin only)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot delete yourself")

        # Soft delete by disabling the account and anonymizing optional fields
        user.is_active = False
        user.email = user.email or None
        user.full_name = user.full_name or None

        db.commit()
        db.refresh(user)

        audit = AuditLog(
            user_id=current_user.id,
            action="soft_delete_user",
            resource_type="user",
            resource_id=user_id,
            details_json={"username": user.username, "is_active": user.is_active}
        )
        db.add(audit)
        db.commit()

        return {"message": "User deactivated (soft delete)", "deactivated": True}

    except Exception as e:
        db.rollback()
        import logging
        logging.getLogger(__name__).error(f"Error deleting user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")
