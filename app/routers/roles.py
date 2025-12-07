from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models import Role, User
from app.services.auth_service import get_current_user, require_admin

router = APIRouter(prefix="/api/roles", tags=["roles"])

# Pydantic models
class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str] = []

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    description: Optional[str] = None
    permissions: Optional[List[str]] = None

class RoleResponse(RoleBase):
    id: uuid.UUID
    is_custom: bool

    class Config:
        from_attributes = True

@router.get("", response_model=List[RoleResponse])
def get_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all available roles."""
    return db.query(Role).order_by(Role.name).all()

@router.post("", response_model=RoleResponse)
def create_role(
    role: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new custom role."""
    # Check if exists
    if db.query(Role).filter(Role.name == role.name).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{role.name}' already exists"
        )
    
    new_role = Role(
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        is_custom=True
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role

@router.put("/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: uuid.UUID,
    role_update: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update an existing role."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Prevent modifying critical built-in roles' names (though we only allow updating desc/perms here)
    # Ideally, we might want to restrict modifying permissions of built-in roles too, 
    # but for flexibility we might allow it. Let's block it for now for safety if it's not custom.
    # Actually user requirement says "options to ... modify roles", implying even built-ins might be tweakable?
    # Best practice: Don't mess with built-in roles structure to avoid breaking verify logic.
    # But usually description is fine. 
    
    if not role.is_custom and role_update.permissions is not None:
         # Optional: Allow or disallow. 
         # For now, let's allow admins to modify built-in roles if they really want to, 
         # or we can enforce is_custom check.
         # Let's start with allowing update but typically we should warn.
         pass

    if role_update.description is not None:
        role.description = role_update.description
    if role_update.permissions is not None:
        role.permissions = role_update.permissions
    
    db.commit()
    db.refresh(role)
    return role

@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a custom role."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    if not role.is_custom:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete built-in system roles"
        )
    
    # Check if assigned to any user?
    # Simple check: (This relies on User.role being a string matching Role.name)
    # Since we haven't FK'd User.role to Role.id yet (User.role is string), 
    # we check by name match.
    users_with_role = db.query(User).filter(User.role == role.name).count()
    if users_with_role > 0:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete role '{role.name}' because it is assigned to {users_with_role} users."
        )

    db.delete(role)
    db.commit()
