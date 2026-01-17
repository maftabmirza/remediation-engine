"""
Prometheus Datasource Management API
Provides CRUD operations for managing multiple Prometheus instances
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import httpx
import uuid

from app.database import get_db
from app.models_dashboards import PrometheusDatasource
from app.routers.auth import get_current_user
from app.config import get_settings
from cryptography.fernet import Fernet
import base64

router = APIRouter(prefix="/api/datasources", tags=["Datasources"])


# Pydantic schemas
class DatasourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=512)
    description: Optional[str] = None
    auth_type: str = Field(default="none", pattern="^(none|basic|bearer)$")
    username: Optional[str] = None
    password: Optional[str] = None
    bearer_token: Optional[str] = None
    timeout: int = Field(default=30, ge=5, le=300)
    is_default: bool = False
    is_enabled: bool = True
    custom_headers: Optional[dict] = None

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        v = v.rstrip('/')
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class DatasourceCreate(DatasourceBase):
    pass


class DatasourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[str] = Field(None, min_length=1, max_length=512)
    description: Optional[str] = None
    auth_type: Optional[str] = Field(None, pattern="^(none|basic|bearer)$")
    username: Optional[str] = None
    password: Optional[str] = None
    bearer_token: Optional[str] = None
    timeout: Optional[int] = Field(None, ge=5, le=300)
    is_default: Optional[bool] = None
    is_enabled: Optional[bool] = None
    custom_headers: Optional[dict] = None


class DatasourceResponse(BaseModel):
    id: str
    name: str
    url: str
    description: Optional[str]
    auth_type: str
    username: Optional[str]
    timeout: int
    is_default: bool
    is_enabled: bool
    custom_headers: Optional[dict]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


class DatasourceTestResult(BaseModel):
    success: bool
    message: str
    version: Optional[str] = None
    uptime_seconds: Optional[float] = None


# Encryption helpers
def get_encryption_key():
    """Get or generate Fernet encryption key"""
    settings = get_settings()
    if settings.encryption_key:
        return settings.encryption_key.encode()
    # Fallback to generating a key (not recommended for production)
    return Fernet.generate_key()


def encrypt_password(password: str) -> str:
    """Encrypt password using Fernet"""
    if not password:
        return ""
    fernet = Fernet(get_encryption_key())
    return fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    """Decrypt password using Fernet"""
    if not encrypted_password:
        return ""
    try:
        fernet = Fernet(get_encryption_key())
        return fernet.decrypt(encrypted_password.encode()).decode()
    except Exception:
        return ""


# API Endpoints
@router.get("/", response_model=List[DatasourceResponse])
async def list_datasources(
    enabled_only: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    List all Prometheus datasources

    - **enabled_only**: If true, only return enabled datasources
    """
    query = db.query(PrometheusDatasource)

    if enabled_only:
        query = query.filter(PrometheusDatasource.is_enabled == True)

    datasources = query.order_by(
        PrometheusDatasource.is_default.desc(),
        PrometheusDatasource.name
    ).all()

    return datasources


@router.get("/{datasource_id}", response_model=DatasourceResponse)
async def get_datasource(
    datasource_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific datasource by ID"""
    datasource = db.query(PrometheusDatasource).filter(
        PrometheusDatasource.id == datasource_id
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasource {datasource_id} not found"
        )

    return datasource


@router.post("/", response_model=DatasourceResponse, status_code=status.HTTP_201_CREATED)
async def create_datasource(
    datasource: DatasourceCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new Prometheus datasource

    - **name**: Unique name for the datasource
    - **url**: Prometheus server URL (http://host:port)
    - **auth_type**: Authentication type (none, basic, bearer)
    - **is_default**: Set as default datasource (only one can be default)
    """
    # Check for duplicate name
    existing = db.query(PrometheusDatasource).filter(
        PrometheusDatasource.name == datasource.name
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Datasource with name '{datasource.name}' already exists"
        )

    # If setting as default, unset other defaults
    if datasource.is_default:
        db.query(PrometheusDatasource).update({"is_default": False})

    # Encrypt password if provided
    encrypted_password = None
    encrypted_token = None

    if datasource.password:
        encrypted_password = encrypt_password(datasource.password)

    if datasource.bearer_token:
        encrypted_token = encrypt_password(datasource.bearer_token)

    # Create datasource
    new_datasource = PrometheusDatasource(
        id=str(uuid.uuid4()),
        name=datasource.name,
        url=datasource.url,
        description=datasource.description,
        auth_type=datasource.auth_type,
        username=datasource.username,
        password=encrypted_password,
        bearer_token=encrypted_token,
        timeout=datasource.timeout,
        is_default=datasource.is_default,
        is_enabled=datasource.is_enabled,
        custom_headers=datasource.custom_headers,
        created_by=current_user.username
    )

    db.add(new_datasource)
    db.commit()
    db.refresh(new_datasource)

    return new_datasource


@router.put("/{datasource_id}", response_model=DatasourceResponse)
async def update_datasource(
    datasource_id: str,
    datasource_update: DatasourceUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update an existing datasource"""
    datasource = db.query(PrometheusDatasource).filter(
        PrometheusDatasource.id == datasource_id
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasource {datasource_id} not found"
        )

    # Check for duplicate name if name is being changed
    if datasource_update.name and datasource_update.name != datasource.name:
        existing = db.query(PrometheusDatasource).filter(
            PrometheusDatasource.name == datasource_update.name
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Datasource with name '{datasource_update.name}' already exists"
            )

    # If setting as default, unset other defaults
    if datasource_update.is_default:
        db.query(PrometheusDatasource).filter(
            PrometheusDatasource.id != datasource_id
        ).update({"is_default": False})

    # Update fields
    update_data = datasource_update.dict(exclude_unset=True)

    # Handle password encryption
    if "password" in update_data and update_data["password"]:
        update_data["password"] = encrypt_password(update_data["password"])

    if "bearer_token" in update_data and update_data["bearer_token"]:
        update_data["bearer_token"] = encrypt_password(update_data["bearer_token"])

    # Update timestamp
    update_data["updated_at"] = datetime.utcnow()

    for key, value in update_data.items():
        setattr(datasource, key, value)

    db.commit()
    db.refresh(datasource)

    return datasource


@router.delete("/{datasource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_datasource(
    datasource_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a datasource"""
    datasource = db.query(PrometheusDatasource).filter(
        PrometheusDatasource.id == datasource_id
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasource {datasource_id} not found"
        )

    # Check if this is the default datasource
    if datasource.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default datasource. Set another datasource as default first."
        )

    db.delete(datasource)
    db.commit()

    return None


@router.post("/{datasource_id}/test", response_model=DatasourceTestResult)
async def test_datasource(
    datasource_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Test connectivity to a Prometheus datasource

    Returns version info and uptime if successful
    """
    datasource = db.query(PrometheusDatasource).filter(
        PrometheusDatasource.id == datasource_id
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasource {datasource_id} not found"
        )

    # Build auth headers
    headers = {}
    auth = None

    if datasource.auth_type == "basic" and datasource.username:
        password = decrypt_password(datasource.password) if datasource.password else ""
        auth = (datasource.username, password)
    elif datasource.auth_type == "bearer" and datasource.bearer_token:
        token = decrypt_password(datasource.bearer_token)
        headers["Authorization"] = f"Bearer {token}"

    if datasource.custom_headers:
        headers.update(datasource.custom_headers)

    # Test connection
    async with httpx.AsyncClient(timeout=datasource.timeout) as client:
        try:
            # Try to get build info
            response = await client.get(
                f"{datasource.url}/api/v1/status/buildinfo",
                headers=headers,
                auth=auth
            )

            if response.status_code == 200:
                build_info = response.json()
                version = build_info.get("data", {}).get("version", "unknown")

                # Also get runtime info for uptime
                runtime_response = await client.get(
                    f"{datasource.url}/api/v1/status/runtimeinfo",
                    headers=headers,
                    auth=auth
                )

                uptime = None
                if runtime_response.status_code == 200:
                    runtime_data = runtime_response.json()
                    startTime_str = runtime_data.get("data", {}).get("startTime")
                    if startTime_str:
                        try:
                            # Parse RFC3339 string to datetime
                            # Python 3.11+ supports ISO parsing including Z
                            start_dt = datetime.fromisoformat(startTime_str.replace('Z', '+00:00'))
                            uptime = (datetime.now(start_dt.tzinfo) - start_dt).total_seconds()
                        except Exception:
                            uptime = None

                return DatasourceTestResult(
                    success=True,
                    message="Successfully connected to Prometheus",
                    version=version,
                    uptime_seconds=uptime
                )
            else:
                return DatasourceTestResult(
                    success=False,
                    message=f"Failed to connect: HTTP {response.status_code}"
                )

        except httpx.TimeoutException:
            return DatasourceTestResult(
                success=False,
                message=f"Connection timeout after {datasource.timeout}s"
            )
        except httpx.ConnectError:
            return DatasourceTestResult(
                success=False,
                message=f"Cannot connect to {datasource.url}"
            )
        except Exception as e:
            return DatasourceTestResult(
                success=False,
                message=f"Error: {str(e)}"
            )


@router.get("/default/get", response_model=DatasourceResponse)
async def get_default_datasource(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get the default datasource"""
    datasource = db.query(PrometheusDatasource).filter(
        PrometheusDatasource.is_default == True
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default datasource configured"
        )

    return datasource
