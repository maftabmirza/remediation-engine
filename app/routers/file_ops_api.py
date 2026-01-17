"""
File Operations API (Phase 1)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from uuid import UUID
import logging

from app.database import get_db
from app.services.auth_service import get_current_user
from app.models import User
from app.services.file_ops_service import FileOpsService
from app.services.changeset_service import ChangeSetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["files"])

# Pydantic Models
class FileReadRequest(BaseModel):
    server_id: UUID
    file_path: str

class FileWriteRequest(BaseModel):
    server_id: UUID
    file_path: str
    content: str
    create_backup: bool = True

class FileListRequest(BaseModel):
    server_id: UUID
    directory: str
    pattern: str = "*"

class ChangeSetCreateRequest(BaseModel):
    session_id: UUID
    title: str
    description: Optional[str] = None
    agent_step_id: Optional[UUID] = None

class ChangeItemCreateRequest(BaseModel):
    file_path: str
    operation: str  # create, modify, delete, rename
    new_content: Optional[str] = None
    old_content: Optional[str] = None
    diff_hunks: Optional[Dict] = None

class ChangeSetResponse(BaseModel):
    id: UUID
    title: str
    status: str
    created_at: Any
    items: List[Dict] = []

    class Config:
        from_attributes = True

# --- File Operations ---

@router.post("/files/read")
async def read_file(
    request: FileReadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Read contents of a remote file."""
    service = FileOpsService(db)
    try:
        result = await service.read_file(request.server_id, request.file_path)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"Read file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files/write")
async def write_file(
    request: FileWriteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Write contents to a remote file."""
    service = FileOpsService(db)
    try:
        result = await service.write_file(
            request.server_id,
            request.file_path,
            request.content,
            request.create_backup
        )
        return result
    except Exception as e:
        logger.error(f"Write file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files/list")
async def list_files(
    request: FileListRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List files in a remote directory."""
    service = FileOpsService(db)
    try:
        return await service.list_files(
            request.server_id,
            request.directory,
            request.pattern
        )
    except Exception as e:
        logger.error(f"List files error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Change Sets ---

@router.post("/changesets", response_model=ChangeSetResponse)
def create_change_set(
    request: ChangeSetCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new pending change set."""
    file_ops = FileOpsService(db)
    service = ChangeSetService(db, file_ops)
    try:
        changeset = service.create_change_set(
            request.session_id,
            request.title,
            request.description,
            request.agent_step_id
        )
        return changeset
    except Exception as e:
        logger.error(f"Create changeset error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/changesets/{changeset_id}/items")
def add_change_item(
    changeset_id: UUID,
    request: ChangeItemCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a change item to a change set."""
    file_ops = FileOpsService(db)
    service = ChangeSetService(db, file_ops)
    try:
        item = service.add_change_item(
            changeset_id,
            request.file_path,
            request.operation,
            request.new_content,
            request.old_content,
            request.diff_hunks
        )
        return {"id": item.id, "status": "added"}
    except Exception as e:
        logger.error(f"Add change item error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/changesets/{changeset_id}/apply")
async def apply_change_set(
    changeset_id: UUID,
    server_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Apply a pending change set to the server."""
    file_ops = FileOpsService(db)
    service = ChangeSetService(db, file_ops)
    try:
        success = await service.apply_change_set(changeset_id, server_id)
        if success:
            return {"status": "success", "message": "Change set applied"}
        else:
            raise HTTPException(status_code=500, detail="Failed to apply change set")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Apply changeset error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/changesets/{changeset_id}/rollback")
async def rollback_change_set(
    changeset_id: UUID,
    server_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Rollback an applied change set."""
    file_ops = FileOpsService(db)
    service = ChangeSetService(db, file_ops)
    try:
        success = await service.rollback_change_set(changeset_id, server_id)
        if success:
            return {"status": "success", "message": "Change set rolled back"}
        else:
            raise HTTPException(status_code=500, detail="Failed to rollback change set")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Rollback changeset error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
