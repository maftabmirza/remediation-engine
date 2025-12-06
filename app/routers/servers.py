"""
Server Management API endpoints
"""
import socket
import time
from typing import List, Optional
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

class ServerResponse(BaseModel):
    id: UUID
    name: str
    hostname: str
    port: int
    username: str
    auth_type: str
    environment: str
    last_connection_test: Optional[datetime]
    last_connection_status: Optional[str]
    last_connection_error: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ServerTestRequest(BaseModel):
    hostname: str
    port: int = 22
    protocol: str = "ssh"


class ServerTestResponse(BaseModel):
    status: str
    message: str
    latency_ms: Optional[int] = None


def _probe_port(hostname: str, port: int, timeout: float = 5.0) -> ServerTestResponse:
    """Attempt a TCP connection to the host/port to validate reachability."""
    start = time.perf_counter()
    try:
        with socket.create_connection((hostname, port), timeout=timeout):
            latency = int((time.perf_counter() - start) * 1000)
            return ServerTestResponse(status="success", message="Reachable", latency_ms=latency)
    except Exception as exc:  # pragma: no cover - network failures not deterministic
        return ServerTestResponse(status="error", message=str(exc))

@router.get("", response_model=List[ServerResponse])
async def list_servers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available servers. All authenticated users can view servers."""
    return db.query(ServerCredential).all()

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

    probe = _probe_port(data.hostname, data.port)
    tested_at = datetime.utcnow()
    if probe.status != "success":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Connection test failed: {probe.message}")

    server = ServerCredential(
        name=data.name,
        hostname=data.hostname,
        port=data.port,
        username=data.username,
        auth_type=data.auth_type,
        ssh_key_encrypted=ssh_key_enc,
        password_encrypted=password_enc,
        environment=data.environment,
        created_by=current_user.id,
        last_connection_test=tested_at,
        last_connection_status=probe.status,
        last_connection_error=None if probe.status == "success" else probe.message
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


@router.post("/test", response_model=ServerTestResponse)
async def test_server_on_demand(
    payload: ServerTestRequest,
    current_user: User = Depends(require_admin),
):
    """Test a server connection before saving credentials."""
    return _probe_port(payload.hostname, payload.port)


@router.post("/{server_id}/test", response_model=ServerTestResponse)
async def test_saved_server(
    server_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Run a connection test for an existing server and persist the result."""
    server = db.query(ServerCredential).filter(ServerCredential.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    probe = _probe_port(server.hostname, server.port)
    server.last_connection_test = datetime.utcnow()
    server.last_connection_status = probe.status
    server.last_connection_error = None if probe.status == "success" else probe.message
    db.commit()

    audit = AuditLog(
        user_id=current_user.id,
        action="test_server",
        resource_type="server",
        resource_id=server.id,
        details_json={"status": probe.status, "message": probe.message},
    )
    db.add(audit)
    db.commit()

    return probe


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
    
    db.delete(server)
    db.commit()
    
    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action="delete_server",
        resource_type="server",
        resource_id=server_id,
        details_json={"name": server.name}
    )
    db.add(audit)
    db.commit()
    
    return {"message": "Server deleted successfully"}
