"""
Runbook ACL API

Endpoints for managing resource-level permissions on runbooks.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models_group import Group
from app.models_runbook_acl import RunbookACL
from app.models_remediation import Runbook
from app.services.auth_service import get_current_user, require_permission


router = APIRouter(prefix="/api/runbooks", tags=["runbook-acl"])


# --- Schemas ---

class ACLEntryBase(BaseModel):
    group_id: UUID
    can_view: bool = True
    can_edit: bool = False
    can_execute: bool = False


class ACLEntryCreate(ACLEntryBase):
    pass


class ACLEntryResponse(ACLEntryBase):
    id: UUID
    group_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class ACLUpdateRequest(BaseModel):
    """Bulk update ACL entries for a runbook"""
    entries: List[ACLEntryCreate]


# --- Endpoints ---

@router.get("/{runbook_id}/acl", response_model=List[ACLEntryResponse])
async def get_runbook_acl(
    runbook_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get all ACL entries for a runbook"""
    # Verify runbook exists
    runbook = db.query(Runbook).filter(Runbook.id == runbook_id).first()
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    entries = db.query(RunbookACL).filter(RunbookACL.runbook_id == runbook_id).all()
    
    result = []
    for entry in entries:
        group = db.query(Group).filter(Group.id == entry.group_id).first()
        result.append(ACLEntryResponse(
            id=entry.id,
            group_id=entry.group_id,
            group_name=group.name if group else None,
            can_view=entry.can_view,
            can_edit=entry.can_edit,
            can_execute=entry.can_execute
        ))
    
    return result


@router.put("/{runbook_id}/acl", response_model=List[ACLEntryResponse])
async def update_runbook_acl(
    runbook_id: UUID,
    request: ACLUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(["edit_runbooks"]))
):
    """
    Bulk update ACL entries for a runbook.
    Replaces all existing entries with the new list.
    """
    # Verify runbook exists
    runbook = db.query(Runbook).filter(Runbook.id == runbook_id).first()
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    # Delete existing entries
    db.query(RunbookACL).filter(RunbookACL.runbook_id == runbook_id).delete()
    
    # Create new entries
    new_entries = []
    for entry_data in request.entries:
        # Verify group exists
        group = db.query(Group).filter(Group.id == entry_data.group_id).first()
        if not group:
            continue  # Skip invalid groups
        
        acl_entry = RunbookACL(
            runbook_id=runbook_id,
            group_id=entry_data.group_id,
            can_view=entry_data.can_view,
            can_edit=entry_data.can_edit,
            can_execute=entry_data.can_execute,
            created_by=user.id
        )
        db.add(acl_entry)
        new_entries.append(acl_entry)
    
    db.commit()
    
    # Build response
    result = []
    for entry in new_entries:
        group = db.query(Group).filter(Group.id == entry.group_id).first()
        result.append(ACLEntryResponse(
            id=entry.id,
            group_id=entry.group_id,
            group_name=group.name if group else None,
            can_view=entry.can_view,
            can_edit=entry.can_edit,
            can_execute=entry.can_execute
        ))
    
    return result


@router.post("/{runbook_id}/acl", response_model=ACLEntryResponse, status_code=201)
async def add_runbook_acl_entry(
    runbook_id: UUID,
    entry: ACLEntryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(["edit_runbooks"]))
):
    """Add a single ACL entry for a runbook"""
    # Verify runbook exists
    runbook = db.query(Runbook).filter(Runbook.id == runbook_id).first()
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    
    # Verify group exists
    group = db.query(Group).filter(Group.id == entry.group_id).first()
    if not group:
        raise HTTPException(status_code=400, detail="Group not found")
    
    # Check if entry already exists
    existing = db.query(RunbookACL).filter(
        RunbookACL.runbook_id == runbook_id,
        RunbookACL.group_id == entry.group_id
    ).first()
    
    if existing:
        # Update existing
        existing.can_view = entry.can_view
        existing.can_edit = entry.can_edit
        existing.can_execute = entry.can_execute
        db.commit()
        db.refresh(existing)
        return ACLEntryResponse(
            id=existing.id,
            group_id=existing.group_id,
            group_name=group.name,
            can_view=existing.can_view,
            can_edit=existing.can_edit,
            can_execute=existing.can_execute
        )
    
    # Create new entry
    acl_entry = RunbookACL(
        runbook_id=runbook_id,
        group_id=entry.group_id,
        can_view=entry.can_view,
        can_edit=entry.can_edit,
        can_execute=entry.can_execute,
        created_by=user.id
    )
    db.add(acl_entry)
    db.commit()
    db.refresh(acl_entry)
    
    return ACLEntryResponse(
        id=acl_entry.id,
        group_id=acl_entry.group_id,
        group_name=group.name,
        can_view=acl_entry.can_view,
        can_edit=acl_entry.can_edit,
        can_execute=acl_entry.can_execute
    )


@router.delete("/{runbook_id}/acl/{group_id}", status_code=204)
async def remove_runbook_acl_entry(
    runbook_id: UUID,
    group_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(["edit_runbooks"]))
):
    """Remove an ACL entry for a group from a runbook"""
    entry = db.query(RunbookACL).filter(
        RunbookACL.runbook_id == runbook_id,
        RunbookACL.group_id == group_id
    ).first()
    
    if not entry:
        raise HTTPException(status_code=404, detail="ACL entry not found")
    
    db.delete(entry)
    db.commit()
