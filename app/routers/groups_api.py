"""Groups API router for RBAC group management."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models import User, Role
from app.models_group import Group, GroupMember
from app.services.auth_service import get_current_user, require_permission


router = APIRouter(prefix="/api/groups", tags=["groups"])


# Pydantic schemas
class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    role_id: Optional[uuid.UUID] = None


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    role_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None
    ad_group_dn: Optional[str] = None
    sync_enabled: Optional[bool] = None


class MemberAdd(BaseModel):
    user_id: uuid.UUID


class GroupMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    source: str
    joined_at: str

    class Config:
        from_attributes = True


class GroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    role_id: Optional[uuid.UUID]
    role_name: Optional[str] = None
    ad_group_dn: Optional[str]
    sync_enabled: bool
    is_active: bool
    member_count: int = 0
    created_at: str

    class Config:
        from_attributes = True


# API Endpoints
@router.get("", response_model=List[GroupResponse])
def list_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all groups."""
    groups = db.query(Group).order_by(Group.name).all()
    result = []
    for g in groups:
        member_count = db.query(GroupMember).filter(GroupMember.group_id == g.id).count()
        result.append(GroupResponse(
            id=g.id,
            name=g.name,
            description=g.description,
            role_id=g.role_id,
            role_name=g.role.name if g.role else None,
            ad_group_dn=g.ad_group_dn,
            sync_enabled=g.sync_enabled,
            is_active=g.is_active,
            member_count=member_count,
            created_at=g.created_at.isoformat() if g.created_at else ""
        ))
    return result


@router.post("", response_model=GroupResponse)
def create_group(
    group: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(["manage_users"]))
):
    """Create a new group."""
    # Check if name exists
    if db.query(Group).filter(Group.name == group.name).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Group '{group.name}' already exists"
        )
    
    # Validate role if provided
    if group.role_id:
        role = db.query(Role).filter(Role.id == group.role_id).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role_id"
            )
    
    new_group = Group(
        name=group.name,
        description=group.description,
        role_id=group.role_id,
        created_by=current_user.id
    )
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    
    return GroupResponse(
        id=new_group.id,
        name=new_group.name,
        description=new_group.description,
        role_id=new_group.role_id,
        role_name=new_group.role.name if new_group.role else None,
        ad_group_dn=new_group.ad_group_dn,
        sync_enabled=new_group.sync_enabled,
        is_active=new_group.is_active,
        member_count=0,
        created_at=new_group.created_at.isoformat() if new_group.created_at else ""
    )


@router.get("/{group_id}", response_model=GroupResponse)
def get_group(
    group_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific group."""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    member_count = db.query(GroupMember).filter(GroupMember.group_id == group.id).count()
    
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        role_id=group.role_id,
        role_name=group.role.name if group.role else None,
        ad_group_dn=group.ad_group_dn,
        sync_enabled=group.sync_enabled,
        is_active=group.is_active,
        member_count=member_count,
        created_at=group.created_at.isoformat() if group.created_at else ""
    )


@router.put("/{group_id}", response_model=GroupResponse)
def update_group(
    group_id: uuid.UUID,
    group_update: GroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(["manage_users"]))
):
    """Update a group."""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    if group_update.name is not None:
        # Check for duplicate name
        existing = db.query(Group).filter(Group.name == group_update.name, Group.id != group_id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group name already exists")
        group.name = group_update.name
    
    if group_update.description is not None:
        group.description = group_update.description
    
    if group_update.role_id is not None:
        role = db.query(Role).filter(Role.id == group_update.role_id).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role_id")
        group.role_id = group_update.role_id
    
    if group_update.is_active is not None:
        group.is_active = group_update.is_active
    
    if group_update.ad_group_dn is not None:
        group.ad_group_dn = group_update.ad_group_dn
    
    if group_update.sync_enabled is not None:
        group.sync_enabled = group_update.sync_enabled
    
    db.commit()
    db.refresh(group)
    
    member_count = db.query(GroupMember).filter(GroupMember.group_id == group.id).count()
    
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        role_id=group.role_id,
        role_name=group.role.name if group.role else None,
        ad_group_dn=group.ad_group_dn,
        sync_enabled=group.sync_enabled,
        is_active=group.is_active,
        member_count=member_count,
        created_at=group.created_at.isoformat() if group.created_at else ""
    )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(["manage_users"]))
):
    """Delete a group."""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    # Delete all memberships (cascade should handle this, but be explicit)
    db.query(GroupMember).filter(GroupMember.group_id == group_id).delete()
    db.delete(group)
    db.commit()


# Member management
@router.get("/{group_id}/members", response_model=List[GroupMemberResponse])
def list_group_members(
    group_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List members of a group."""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    members = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    result = []
    for m in members:
        result.append(GroupMemberResponse(
            id=m.id,
            user_id=m.user_id,
            username=m.user.username if m.user else "Unknown",
            source=m.source,
            joined_at=m.joined_at.isoformat() if m.joined_at else ""
        ))
    return result


@router.post("/{group_id}/members", response_model=GroupMemberResponse)
def add_member(
    group_id: uuid.UUID,
    member: MemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(["manage_users"]))
):
    """Add a user to a group."""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    
    user = db.query(User).filter(User.id == member.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Check if already a member
    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == member.user_id
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already a member")
    
    new_member = GroupMember(
        group_id=group_id,
        user_id=member.user_id,
        source="manual"
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
    
    return GroupMemberResponse(
        id=new_member.id,
        user_id=new_member.user_id,
        username=user.username,
        source=new_member.source,
        joined_at=new_member.joined_at.isoformat() if new_member.joined_at else ""
    )


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(["manage_users"]))
):
    """Remove a user from a group."""
    membership = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    
    db.delete(membership)
    db.commit()
