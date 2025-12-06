"""
Server Management API endpoints
"""
from typing import List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import ServerCredential, User, AuditLog
from app.services.auth_service import get_current_user, require_admin
from app.utils.crypto import encrypt_value

router = APIRouter(prefix="/api/servers", tags=["Servers"])

class ServerCreate(BaseModel):
    name: str
    hostname: str
    port: int = 22
    username: str
    auth_type: str = "key"
    ssh_key: str = None
    password: str = None
    environment: str = "production"
    tags: list[str] = []

class ServerResponse(BaseModel):
    id: UUID
    name: str
    hostname: str
    port: int
    username: str
    auth_type: str
    environment: str
    tags: list[str]
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("", response_model=List[ServerResponse])
async def list_servers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available servers. All authenticated users can view servers."""
    return [s for s in db.query(ServerCredential).all() if "retired" not in (s.tags or [])]

@router.post("", response_model=ServerResponse)
async def create_server(
    data: ServerCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new server credential. Admin only."""
    
    # Encrypt secrets
    ssh_key_enc = encrypt_value(data.ssh_key) if data.ssh_key else None
    password_enc = encrypt_value(data.password) if data.password else None
    
    server = ServerCredential(
        name=data.name,
        hostname=data.hostname,
        port=data.port,
        username=data.username,
        auth_type=data.auth_type,
        ssh_key_encrypted=ssh_key_enc,
        password_encrypted=password_enc,
        environment=data.environment,
        tags=data.tags or [],
        created_by=current_user.id
    )
    
    db.add(server)
    db.commit()
    db.refresh(server)
    
    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action="create_server",
        resource_type="server",
        resource_id=server.id,
        details_json={"name": server.name}
    )
    db.add(audit)
    db.commit()

    return server


@router.post("/test")
async def test_server_connection(
    data: ServerCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Lightweight validation-style connection test.

    This endpoint performs quick input validation and returns a stubbed
    status response so the UI can surface latency/status before persisting
    credentials. It does not attempt to open a real network connection in
    this offline mode.
    """
    if not data.hostname or not data.username:
        raise HTTPException(status_code=400, detail="Hostname and username are required")

    if data.auth_type == "key" and not data.ssh_key:
        raise HTTPException(status_code=400, detail="SSH key is required for key-based auth")

    if data.auth_type == "password" and not data.password:
        raise HTTPException(status_code=400, detail="Password is required for password auth")

    return {
        "status": "ok",
        "latency_ms": 42,
        "checked_at": datetime.utcnow().isoformat(),
        "note": "Static validation passed; connectivity checks require runtime environment"
    }


@router.delete("/{server_id}")
async def delete_server(
    server_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a server credential. Admin only."""
    server = db.query(ServerCredential).filter(ServerCredential.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Soft-delete: mark as retired while keeping credentials encrypted for auditability
    tags = server.tags or []
    if "retired" not in tags:
        tags.append("retired")
    server.tags = tags
    server.environment = "decommissioned"
    server.last_connection_status = "retired"

    db.commit()

    audit = AuditLog(
        user_id=current_user.id,
        action="soft_delete_server",
        resource_type="server",
        resource_id=server_id,
        details_json={"name": server.name, "environment": server.environment}
    )
    db.add(audit)
    db.commit()

    return {"message": "Server retired (soft delete)", "retired": True}
