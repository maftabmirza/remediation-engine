"""
Dashboard Permissions API

API endpoints for managing fine-grained dashboard access control.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid

from app.database import get_db
from app.models_dashboards import DashboardPermission, Dashboard
from app.routers.auth import get_current_user
from app.models import User

router = APIRouter(
    prefix="/api/dashboards",
    tags=["dashboard_permissions"]
)


# Pydantic schemas
class PermissionCreate(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None  # admin, editor, viewer
    permission: str  # view, edit, admin


class PermissionResponse(BaseModel):
    id: str
    dashboard_id: str
    user_id: Optional[str]
    role: Optional[str]
    permission: str
    created_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


@router.post("/{dashboard_id}/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def create_permission(
    dashboard_id: str,
    perm_data: PermissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Grant permission to a user or role for a dashboard.
    Requires admin permission on the dashboard.
    """
    # Check dashboard exists
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    # Validate: must specify either user_id or role, not both
    if not perm_data.user_id and not perm_data.role:
        raise HTTPException(status_code=400, detail="Must specify either user_id or role")
    if perm_data.user_id and perm_data.role:
        raise HTTPException(status_code=400, detail="Cannot specify both user_id and role")

    # Validate permission level
    if perm_data.permission not in ['view', 'edit', 'admin']:
        raise HTTPException(status_code=400, detail="Permission must be 'view', 'edit', or 'admin'")

    # Check if permission already exists
    existing = db.query(DashboardPermission).filter(
        DashboardPermission.dashboard_id == dashboard_id,
        DashboardPermission.user_id == perm_data.user_id if perm_data.user_id else None,
        DashboardPermission.role == perm_data.role if perm_data.role else None
    ).first()

    if existing:
        # Update existing permission
        existing.permission = perm_data.permission
        db.commit()
        db.refresh(existing)
        return existing

    # Create new permission
    new_permission = DashboardPermission(
        id=str(uuid.uuid4()),
        dashboard_id=dashboard_id,
        user_id=perm_data.user_id,
        role=perm_data.role,
        permission=perm_data.permission,
        created_by=current_user.username
    )

    db.add(new_permission)
    db.commit()
    db.refresh(new_permission)

    return new_permission


@router.get("/{dashboard_id}/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    dashboard_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all permissions for a dashboard."""
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    permissions = db.query(DashboardPermission).filter(
        DashboardPermission.dashboard_id == dashboard_id
    ).all()

    return permissions


@router.delete("/{dashboard_id}/permissions/{permission_id}")
async def delete_permission(
    dashboard_id: str,
    permission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke a permission.
    Requires admin permission on the dashboard.
    """
    permission = db.query(DashboardPermission).filter(
        DashboardPermission.id == permission_id,
        DashboardPermission.dashboard_id == dashboard_id
    ).first()

    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")

    db.delete(permission)
    db.commit()

    return {"message": "Permission revoked successfully"}


@router.get("/{dashboard_id}/check-permission")
async def check_permission(
    dashboard_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check current user's permission level for a dashboard.
    Returns the highest permission level the user has.
    """
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    # Admin users have full access
    if current_user.role == 'admin':
        return {"permission": "admin", "source": "role"}

    # Check user-specific permission
    user_perm = db.query(DashboardPermission).filter(
        DashboardPermission.dashboard_id == dashboard_id,
        DashboardPermission.user_id == str(current_user.id)
    ).first()

    if user_perm:
        return {"permission": user_perm.permission, "source": "user"}

    # Check role-based permission
    role_perm = db.query(DashboardPermission).filter(
        DashboardPermission.dashboard_id == dashboard_id,
        DashboardPermission.role == current_user.role
    ).first()

    if role_perm:
        return {"permission": role_perm.permission, "source": "role"}

    # Default: public dashboards can be viewed by anyone
    if dashboard.is_public:
        return {"permission": "view", "source": "public"}

    return {"permission": None, "source": "none"}
