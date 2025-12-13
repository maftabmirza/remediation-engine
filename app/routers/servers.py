"""
Server Management API endpoints
"""
import json
import socket
import time
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import yaml

from app.database import get_db
from app.models import ServerCredential, User, AuditLog, ServerGroup, CredentialProfile
from app.services.auth_service import require_permission
from app.services.executor_factory import ExecutorFactory
from app.utils.crypto import encrypt_value, decrypt_value

router = APIRouter(prefix="/api/servers", tags=["Servers"])

class ServerBase(BaseModel):
    name: str
    hostname: str
    port: int = 22
    username: str
    auth_type: str = "key"
    environment: str = "production"
    group_id: Optional[UUID] = None
    credential_source: str = "inline"
    credential_profile_id: Optional[UUID] = None
    credential_metadata: dict = {}
    os_type: str = "linux"
    protocol: str = "ssh"
    winrm_transport: Optional[str] = None
    winrm_use_ssl: bool = True
    winrm_cert_validation: bool = True
    domain: Optional[str] = None
    tags: List[str] = []

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "name": "prod-db-01",
                    "hostname": "10.0.0.5",
                    "port": 22,
                    "username": "ec2-user",
                    "auth_type": "key",
                    "credential_source": "inline",
                    "tags": ["production", "database"],
                }
            ]
        }


class ServerCreate(ServerBase):
    ssh_key: Optional[str] = None
    password: Optional[str] = None

class ServerUpdate(BaseModel):
    name: Optional[str] = None
    hostname: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    auth_type: Optional[str] = None
    ssh_key: Optional[str] = None
    password: Optional[str] = None
    environment: Optional[str] = None
    group_id: Optional[UUID] = None
    credential_source: Optional[str] = None
    credential_profile_id: Optional[UUID] = None
    credential_metadata: Optional[dict] = None
    os_type: Optional[str] = None
    protocol: Optional[str] = None
    winrm_transport: Optional[str] = None
    winrm_use_ssl: Optional[bool] = None
    winrm_cert_validation: Optional[bool] = None
    domain: Optional[str] = None
    tags: Optional[List[str]] = None


class ServerTestRequest(BaseModel):
    hostname: str
    port: int = 22
    protocol: str = "ssh"
    username: Optional[str] = None
    auth_type: str = "key"  # key or password
    # For inline credentials
    password: Optional[str] = None
    ssh_key: Optional[str] = None
    # For shared credentials
    credential_source: str = "inline"
    credential_profile_id: Optional[UUID] = None


class ServerTestResponse(BaseModel):
    status: str
    message: str
    latency_ms: Optional[int] = None


class ServerBulkImportRequest(BaseModel):
    format: str = "yaml"  # yaml or json
    content: str
    default_group_id: Optional[UUID] = None
    default_auth_type: str = "key"


class ServerBulkImportResponse(BaseModel):
    created: int
    errors: List[str] = []


class ServerResponse(BaseModel):
    id: UUID
    name: str
    hostname: str
    port: int
    username: str
    auth_type: str
    environment: str
    group_id: Optional[UUID] = None
    group_path: Optional[str] = None
    credential_source: Optional[str] = None
    credential_profile_id: Optional[UUID] = None
    credential_profile_name: Optional[str] = None
    credential_metadata: dict = {}
    os_type: Optional[str] = None
    protocol: Optional[str] = None
    tags: List[str] = []
    last_connection_test: Optional[datetime]
    last_connection_status: Optional[str]
    last_connection_error: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


def serialize_server(server: ServerCredential) -> ServerResponse:
    payload = ServerResponse.model_validate(server)
    payload.group_id = server.group_id
    payload.group_path = server.group.path if server.group else None
    payload.credential_profile_id = server.credential_profile_id
    payload.credential_profile_name = server.credential_profile.name if server.credential_profile else None
    payload.credential_metadata = server.credential_metadata or {}
    return payload


def _build_server_entity(data: ServerCreate, current_user: User, db: Session) -> ServerCredential:
    if data.group_id:
        group = db.query(ServerGroup).filter(ServerGroup.id == data.group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Server group not found")

    if data.credential_source == "shared_profile":
        if not data.credential_profile_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shared credentials require a profile selection")
        profile = db.query(CredentialProfile).filter(CredentialProfile.id == data.credential_profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Credential profile not found")
    elif data.credential_profile_id:
        profile = db.query(CredentialProfile).filter(CredentialProfile.id == data.credential_profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Credential profile not found")

    # Encrypt secrets
    ssh_key_enc = encrypt_value(data.ssh_key) if data.ssh_key else None
    password_enc = encrypt_value(data.password) if data.password else None

    if data.credential_source == "inline" and not (ssh_key_enc or password_enc) and not data.credential_profile_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inline credentials require a password or SSH key")

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
        os_type=data.os_type,
        protocol=data.protocol,
        winrm_transport=data.winrm_transport,
        winrm_use_ssl=data.winrm_use_ssl,
        winrm_cert_validation=data.winrm_cert_validation,
        domain=data.domain,
        ssh_key_encrypted=ssh_key_enc,
        password_encrypted=password_enc,
        credential_source=data.credential_source,
        credential_profile_id=data.credential_profile_id,
        credential_metadata=data.credential_metadata,
        environment=data.environment,
        tags=data.tags,
        group_id=data.group_id,
        created_by=current_user.id,
        last_connection_test=tested_at,
        last_connection_status=probe.status,
        last_connection_error=None if probe.status == "success" else probe.message,
    )
    return server


class ServerGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[UUID] = None


class ServerGroupResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    parent_id: Optional[UUID]
    path: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CredentialProfileCreate(BaseModel):
    name: str
    description: Optional[str] = None
    username: Optional[str] = None
    credential_type: str = "key"  # key, password, vault, cyberark
    backend: str = "inline"  # inline, vault, cyberark
    secret_value: Optional[str] = None
    metadata_json: dict = {}
    group_id: Optional[UUID] = None


class CredentialProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    username: Optional[str] = None
    credential_type: Optional[str] = None
    backend: Optional[str] = None
    secret_value: Optional[str] = None
    metadata_json: Optional[dict] = None
    group_id: Optional[UUID] = None


class CredentialProfileResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    username: Optional[str]
    credential_type: str
    backend: str
    has_secret: bool = False
    metadata_json: dict = {}
    last_rotated: Optional[datetime]
    group_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True


def _probe_port(hostname: str, port: int, timeout: float = 5.0) -> ServerTestResponse:
    """Attempt a TCP connection to the host/port to validate reachability."""
    start = time.perf_counter()
    try:
        with socket.create_connection((hostname, port), timeout=timeout):
            latency = int((time.perf_counter() - start) * 1000)
            return ServerTestResponse(status="success", message="Reachable", latency_ms=latency)
    except Exception as exc:  # pragma: no cover - network failures not deterministic
        return ServerTestResponse(status="error", message=str(exc))


@router.get("/groups", response_model=List[ServerGroupResponse])
async def list_server_groups(
    current_user: User = Depends(require_permission(["read"])),
    db: Session = Depends(get_db)
):
    """Return available server groups for assignment and navigation."""
    groups = db.query(ServerGroup).all()
    return groups


@router.post("/groups", response_model=ServerGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_server_group(
    payload: ServerGroupCreate,
    current_user: User = Depends(require_permission(["manage_server_groups"])),
    db: Session = Depends(get_db)
):
    """Create a new server group, optionally nested under a parent group."""
    parent = None
    if payload.parent_id:
        parent = db.query(ServerGroup).filter(ServerGroup.id == payload.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent group not found")

    path = payload.name if not parent else f"{parent.path or parent.name}/{payload.name}"
    group = ServerGroup(
        name=payload.name,
        description=payload.description,
        parent_id=payload.parent_id,
        path=path,
    )

    db.add(group)
    db.commit()
    db.refresh(group)

    audit = AuditLog(
        user_id=current_user.id,
        action="create_server_group",
        resource_type="server_group",
        resource_id=group.id,
        details_json={"name": group.name, "parent_id": str(group.parent_id) if group.parent_id else None},
    )
    db.add(audit)
    db.commit()

    return group


@router.get("/credentials", response_model=List[CredentialProfileResponse])
async def list_credential_profiles(
    group_id: Optional[UUID] = None,
    current_user: User = Depends(require_permission(["read"])),
    db: Session = Depends(get_db)
):
    query = db.query(CredentialProfile)
    if group_id:
        query = query.filter(CredentialProfile.group_id == group_id)
    profiles = query.all()
    enriched = []
    for profile in profiles:
        data = CredentialProfileResponse.model_validate(profile)
        data.has_secret = profile.secret_encrypted is not None
        enriched.append(data)
    return enriched


@router.post("/credentials", response_model=CredentialProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_credential_profile(
    payload: CredentialProfileCreate,
    current_user: User = Depends(require_permission(["manage_servers"])),
    db: Session = Depends(get_db),
):
    """Create reusable credential profile, including vault or CyberArk references."""
    if payload.credential_type == "password" and not payload.username:
        raise HTTPException(status_code=400, detail="Password credentials require a username")
    if payload.credential_type == "password" and payload.backend == "inline" and not payload.secret_value:
        raise HTTPException(status_code=400, detail="Password credentials require a secret")
    secret_encrypted = encrypt_value(payload.secret_value) if payload.secret_value else None
    profile = CredentialProfile(
        name=payload.name,
        description=payload.description,
        username=payload.username,
        credential_type=payload.credential_type,
        backend=payload.backend,
        secret_encrypted=secret_encrypted,
        metadata_json=payload.metadata_json,
        last_rotated=datetime.utcnow() if payload.secret_value else None,
        group_id=payload.group_id,
        created_by=current_user.id,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    audit = AuditLog(
        user_id=current_user.id,
        action="create_credential_profile",
        resource_type="credential_profile",
        resource_id=profile.id,
        details_json={"name": profile.name, "backend": profile.backend},
    )
    db.add(audit)
    db.commit()

    response = CredentialProfileResponse.model_validate(profile)
    response.has_secret = profile.secret_encrypted is not None
    return response


@router.put("/credentials/{profile_id}", response_model=CredentialProfileResponse)
async def update_credential_profile(
    profile_id: UUID,
    payload: CredentialProfileUpdate,
    current_user: User = Depends(require_permission(["manage_servers"])),
    db: Session = Depends(get_db),
):
    profile = db.query(CredentialProfile).filter(CredentialProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Credential profile not found")

    if payload.group_id:
        group = db.query(ServerGroup).filter(ServerGroup.id == payload.group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Server group not found")

    if payload.secret_value:
        profile.secret_encrypted = encrypt_value(payload.secret_value)
        profile.last_rotated = datetime.utcnow()

    for field in ["name", "description", "username", "credential_type", "backend", "metadata_json", "group_id"]:
        value = getattr(payload, field, None)
        if value is not None:
            setattr(profile, field, value)

    final_type = profile.credential_type
    final_backend = profile.backend
    if final_type == "password" and not profile.username:
        raise HTTPException(status_code=400, detail="Password credentials require a username")
    if final_type == "password" and final_backend == "inline" and not (profile.secret_encrypted or payload.secret_value):
        raise HTTPException(status_code=400, detail="Password credentials require a secret")

    db.commit()
    db.refresh(profile)

    audit = AuditLog(
        user_id=current_user.id,
        action="update_credential_profile",
        resource_type="credential_profile",
        resource_id=profile.id,
        details_json={"name": profile.name, "backend": profile.backend},
    )
    db.add(audit)
    db.commit()

    response = CredentialProfileResponse.model_validate(profile)
    response.has_secret = profile.secret_encrypted is not None
    return response


@router.delete("/credentials/{profile_id}")
async def delete_credential_profile(
    profile_id: UUID,
    current_user: User = Depends(require_permission(["manage_servers"])),
    db: Session = Depends(get_db),
):
    profile = db.query(CredentialProfile).filter(CredentialProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Credential profile not found")

    in_use = db.query(ServerCredential).filter(ServerCredential.credential_profile_id == profile_id).count()
    if in_use:
        raise HTTPException(status_code=400, detail="Profile is attached to one or more servers")

    db.delete(profile)
    db.commit()

    audit = AuditLog(
        user_id=current_user.id,
        action="delete_credential_profile",
        resource_type="credential_profile",
        resource_id=profile_id,
        details_json={"name": profile.name},
    )
    db.add(audit)
    db.commit()

    return {"message": "Credential profile deleted"}

@router.get("", response_model=List[ServerResponse])
async def list_servers(
    current_user: User = Depends(require_permission(["read"])),
    db: Session = Depends(get_db)
):
    """List available servers. All authenticated users can view servers."""
    servers = db.query(ServerCredential).all()
    return [serialize_server(s) for s in servers]

@router.post("", response_model=ServerResponse)
async def create_server(
    data: ServerCreate,
    current_user: User = Depends(require_permission(["manage_servers"])),
    db: Session = Depends(get_db)
):
    """Create a new server credential. Admin only."""
    server = _build_server_entity(data, current_user, db)

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

    return serialize_server(server)


@router.put("/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: UUID,
    payload: ServerUpdate,
    current_user: User = Depends(require_permission(["manage_servers"])),
    db: Session = Depends(get_db),
):
    server = db.query(ServerCredential).filter(ServerCredential.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
 
    if payload.group_id:
        group = db.query(ServerGroup).filter(ServerGroup.id == payload.group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Server group not found")

    if payload.credential_source == "shared_profile" or payload.credential_profile_id:
        profile_id = payload.credential_profile_id or server.credential_profile_id
        if not profile_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shared credentials require a profile selection")
        profile = db.query(CredentialProfile).filter(CredentialProfile.id == profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Credential profile not found")

    if payload.credential_source == "shared_profile":
        server.ssh_key_encrypted = None
        server.password_encrypted = None
        if payload.credential_profile_id:
            server.credential_profile_id = payload.credential_profile_id
    elif payload.credential_source == "inline":
        server.credential_profile_id = None

    if payload.ssh_key:
        server.ssh_key_encrypted = encrypt_value(payload.ssh_key)
        server.credential_source = "inline"
    if payload.password:
        server.password_encrypted = encrypt_value(payload.password)
        server.credential_source = "inline"
    if payload.credential_source:
        server.credential_source = payload.credential_source
    if payload.credential_profile_id:
        server.credential_profile_id = payload.credential_profile_id
    if payload.credential_metadata is not None:
        server.credential_metadata = payload.credential_metadata

    if payload.credential_source == "inline":
        if not (payload.ssh_key or payload.password or server.ssh_key_encrypted or server.password_encrypted):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inline credentials require an SSH key or password")

    for field in [
        "name",
        "hostname",
        "port",
        "username",
        "auth_type",
        "environment",
        "group_id",
        "os_type",
        "protocol",
        "winrm_transport",
        "winrm_use_ssl",
        "winrm_cert_validation",
        "domain",
    ]:
        value = getattr(payload, field, None)
        if value is not None:
            setattr(server, field, value)

    if payload.tags is not None:
        server.tags = payload.tags

    if payload.hostname or payload.port:
        probe = _probe_port(server.hostname, server.port)
        server.last_connection_test = datetime.utcnow()
        server.last_connection_status = probe.status
        server.last_connection_error = None if probe.status == "success" else probe.message
        if probe.status != "success":
            db.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Connection test failed: {probe.message}")

    db.commit()
    db.refresh(server)

    audit = AuditLog(
        user_id=current_user.id,
        action="update_server",
        resource_type="server",
        resource_id=server.id,
        details_json={"name": server.name},
    )
    db.add(audit)
    db.commit()

    return serialize_server(server)


@router.post("/test", response_model=ServerTestResponse)
async def test_server_on_demand(
    payload: ServerTestRequest,
    current_user: User = Depends(require_permission(["manage_servers"])),
    db: Session = Depends(get_db),
):
    """Test a server connection with provided credentials before saving."""
    try:
        # Check for shared profile if requested
        profile = None
        if payload.credential_source == "shared_profile" and payload.credential_profile_id:
            profile = db.query(CredentialProfile).filter(CredentialProfile.id == payload.credential_profile_id).first()
            if not profile:
                 return ServerTestResponse(status="error", message="Credential profile not found")

        # Construct a temporary server object for the executor
        server = ServerCredential(
            name="test-server",
            hostname=payload.hostname,
            port=payload.port,
            username=payload.username or "root",
            protocol=payload.protocol,
            auth_type=payload.auth_type,
            credential_source=payload.credential_source,
            credential_profile_id=payload.credential_profile_id,
            credential_profile=profile
        )
        
        # Set inline credentials if needed
        if payload.credential_source == "inline":
            if payload.password:
                # Executor factory expects encrypted values (it decrypts them)
                # But here we have raw values. This is a bit tricky.
                # We should probably update factory to handle raw values or hack it here.
                # Hack: Encrypt them temporarily since factory decrypts them.
                server.password_encrypted = encrypt_value(payload.password)
            
            if payload.ssh_key:
                server.ssh_key_encrypted = encrypt_value(payload.ssh_key)

        # Use the executor factory to test connection
        try:
            result = await ExecutorFactory.test_server_connection(server)
            
            status_code = "success" if result.success else "error"
            message = result.stdout if result.success else (result.error_message or result.stderr)
            
            return ServerTestResponse(
                status=status_code,
                message=message or "Connection successful",
                latency_ms=result.duration_ms
            )
        except Exception as e:
            return ServerTestResponse(status="error", message=str(e))
    except Exception as e:
        # Catch all other exceptions and return proper JSON
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Unexpected error in test_server_on_demand: {e}")
        return ServerTestResponse(
            status="error",
            message=f"Internal error: {str(e)}"
        )


@router.post("/import", response_model=ServerBulkImportResponse)
async def bulk_import_servers(
    payload: ServerBulkImportRequest,
    current_user: User = Depends(require_permission(["manage_servers"])),
    db: Session = Depends(get_db),
):
    """Bulk import servers from YAML or JSON payloads."""
    try:
        if payload.format.lower() == "yaml":
            parsed = yaml.safe_load(payload.content) or []
        else:
            parsed = json.loads(payload.content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {payload.format} payload: {exc}")

    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail="Import content must be a list of servers")

    created = 0
    errors: List[str] = []

    for idx, entry in enumerate(parsed):
        try:
            base = {
                "group_id": payload.default_group_id,
                "auth_type": payload.default_auth_type,
                **(entry or {}),
            }
            server_data = ServerCreate(**base)
            server_entity = _build_server_entity(server_data, current_user, db)
            db.add(server_entity)
            db.commit()
            created += 1
        except HTTPException as http_exc:
            db.rollback()
            errors.append(f"Row {idx + 1}: {http_exc.detail}")
        except Exception as exc:
            db.rollback()
            errors.append(f"Row {idx + 1}: {exc}")

    return ServerBulkImportResponse(created=created, errors=errors)


@router.post("/{server_id}/test", response_model=ServerTestResponse)
async def test_saved_server(
    server_id: UUID,
    current_user: User = Depends(require_permission(["manage_servers"])),
    db: Session = Depends(get_db),
):
    """Run a connection test for an existing server and persist the result."""
    try:
        server = db.query(ServerCredential).filter(ServerCredential.id == server_id).first()
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        
        # Use executor factory for real test
        try:
            result = await ExecutorFactory.test_server_connection(server)
            
            status_code = "success" if result.success else "error"
            message = result.stdout if result.success else (result.error_message or result.stderr)
            
            probe = ServerTestResponse(
                status=status_code, 
                message=message or "Connection successful", 
                latency_ms=result.duration_ms
            )
        except Exception as e:
            probe = ServerTestResponse(status="error", message=str(e))
        
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
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch all other exceptions and return proper JSON
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Unexpected error testing server {server_id}: {e}")
        return ServerTestResponse(
            status="error",
            message=f"Internal error: {str(e)}"
        )


class CommandExecuteRequest(BaseModel):
    """Request to execute a command on a server."""
    command: str
    timeout: int = 60  # seconds


class CommandExecuteResponse(BaseModel):
    """Response from command execution."""
    success: bool
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: Optional[int] = None
    error: Optional[str] = None


@router.post("/{server_id}/execute", response_model=CommandExecuteResponse)
async def execute_command(
    server_id: UUID,
    payload: CommandExecuteRequest,
    current_user: User = Depends(require_permission(["read"])),
    db: Session = Depends(get_db),
):
    """
    Execute a command on a server via SSH and return clean output.
    
    This provides clean stdout/stderr capture without terminal escape codes,
    making it ideal for command output that needs to be analyzed by AI.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        server = db.query(ServerCredential).filter(ServerCredential.id == server_id).first()
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        
        # Use ExecutorFactory to run the command
        try:
            result = await ExecutorFactory.execute_command(
                server=server,
                command=payload.command,
                timeout=payload.timeout,
                use_sudo=False  # Let the command include sudo if needed
            )
            
            return CommandExecuteResponse(
                success=result.success,
                exit_code=result.exit_code,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                duration_ms=result.duration_ms,
                error=result.error_message
            )
        except Exception as e:
            logger.warning(f"Command execution failed on {server_id}: {e}")
            return CommandExecuteResponse(
                success=False,
                stdout="",
                stderr="",
                error=str(e)
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error executing command on server {server_id}: {e}")
        return CommandExecuteResponse(
            success=False,
            error=f"Internal error: {str(e)}"
        )


@router.delete("/{server_id}")
async def delete_server(
    server_id: UUID,
    current_user: User = Depends(require_permission(["manage_servers"])),
    db: Session = Depends(get_db)
):
    """Delete a server credential. Admin only."""
    server = db.query(ServerCredential).filter(ServerCredential.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Cleanup dependencies
    # 1. Terminal Sessions
    try:
        from app.models import TerminalSession
        db.query(TerminalSession).filter(TerminalSession.server_credential_id == server_id).delete(synchronize_session=False)
    except Exception:
        pass

    # 2. Runbooks
    try:
        from app.models_remediation import Runbook
        db.query(Runbook).filter(Runbook.default_server_id == server_id).update({Runbook.default_server_id: None}, synchronize_session=False)
    except ImportError:
        pass

    # 3. Executions
    try:
        from app.models_remediation import RunbookExecution
        db.query(RunbookExecution).filter(RunbookExecution.server_id == server_id).update({RunbookExecution.server_id: None}, synchronize_session=False)
    except ImportError:
        pass

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
