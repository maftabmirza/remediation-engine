"""
User Management API endpoints
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, AuditLog, Alert, AutoAnalyzeRule, ServerCredential, SystemConfig, TerminalSession
from app.models_chat import ChatSession
from app.schemas import UserCreate, UserUpdate, UserResponse
from app.services.auth_service import (
    require_permission,
    get_password_hash,
    get_user_by_username,
    get_permissions_for_role,
    VALID_ROLES,
    normalize_role,
)

router = APIRouter(prefix="/api/users", tags=["Users"])


def serialize_user(user: User) -> UserResponse:
    payload = UserResponse.model_validate(user)
    payload.permissions = list(get_permissions_for_role(user.role))
    return payload

@router.get("", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(require_permission(["manage_users"])),
    db: Session = Depends(get_db)
):
    """List all users (Admin only)"""
    users = db.query(User).all()
    return [serialize_user(u) for u in users]

@router.post("", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    current_user: User = Depends(require_permission(["manage_users"])),
    db: Session = Depends(get_db)
):
    """Create a new user (Admin only)"""
    if get_user_by_username(db, data.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    normalized_role = normalize_role(data.role)
    if normalized_role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role selection")

    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        password_hash=get_password_hash(data.password),
        role=normalized_role,
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
    
    return serialize_user(user)

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    current_user: User = Depends(require_permission(["manage_users"])),
    db: Session = Depends(get_db)
):
    """Update a user (Admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if data.password:
        user.password_hash = get_password_hash(data.password)
    if data.role:
        normalized_role = normalize_role(data.role)
        if normalized_role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role selection")
        user.role = normalized_role
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
    
    return serialize_user(user)

@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_permission(["manage_users"])),
    db: Session = Depends(get_db)
):
    """Delete a user (Admin only)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot delete yourself")
        
        # 1. Nullify references in tables where user_id is nullable
        # Use synchronize_session=False for better performance and to avoid issues with expired objects
        db.query(Alert).filter(Alert.analyzed_by == user_id).update({Alert.analyzed_by: None}, synchronize_session=False)
        db.query(AutoAnalyzeRule).filter(AutoAnalyzeRule.created_by == user_id).update({AutoAnalyzeRule.created_by: None}, synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.user_id == user_id).update({AuditLog.user_id: None}, synchronize_session=False)
        db.query(ServerCredential).filter(ServerCredential.created_by == user_id).update({ServerCredential.created_by: None}, synchronize_session=False)
        db.query(SystemConfig).filter(SystemConfig.updated_by == user_id).update({SystemConfig.updated_by: None}, synchronize_session=False)
        
        # 2. Delete records where user_id is NOT nullable (Cascade)
        # Explicitly delete chat messages first if cascade is not working
        from app.models_chat import ChatMessage
        subquery = db.query(ChatSession.id).filter(ChatSession.user_id == user_id)
        db.query(ChatMessage).filter(ChatMessage.session_id.in_(subquery)).delete(synchronize_session=False)
        
        db.query(ChatSession).filter(ChatSession.user_id == user_id).delete(synchronize_session=False)
        db.query(TerminalSession).filter(TerminalSession.user_id == user_id).delete(synchronize_session=False)
        
        # 3. Delete the user
        db.delete(user)
        db.commit()
        
        # Audit (Create a new log entry, but user_id will be current_user, which is fine)
        audit = AuditLog(
            user_id=current_user.id,
            action="delete_user",
            resource_type="user",
            resource_id=user_id,
            details_json={"username": user.username}
        )
        db.add(audit)
        db.commit()
        
        return {"message": "User deleted successfully"}
        
    except Exception as e:
        db.rollback()
        import logging
        logging.getLogger(__name__).error(f"Error deleting user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")
