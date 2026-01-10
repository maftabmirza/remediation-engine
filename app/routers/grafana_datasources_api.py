"""
Grafana Datasources API

REST API for managing observability datasources (Loki, Tempo, Prometheus, Mimir, etc.)
Provides CRUD operations, health checks, and connection testing.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone
import time

from app.database import get_db
from app.models_application import GrafanaDatasource
from app.schemas_grafana_datasource import (
    GrafanaDatasourceCreate,
    GrafanaDatasourceUpdate,
    GrafanaDatasourceResponse,
    GrafanaDatasourceListResponse,
    DatasourceHealthCheckResponse,
    DatasourceTestConnectionRequest,
    DatasourceTestConnectionResponse
)
from app.services.loki_client import LokiClient
from app.services.tempo_client import TempoClient
from app.services.auth_service import get_current_user
from app.models import User

router = APIRouter(
    prefix="/api/grafana-datasources",
    tags=["grafana-datasources"]
)


# ============================================================================
# Helper Functions
# ============================================================================

async def test_datasource_connection(
    datasource_type: str,
    url: str,
    timeout: int = 30,
    auth_type: str = "none",
    username: Optional[str] = None,
    password: Optional[str] = None,
    bearer_token: Optional[str] = None
) -> Tuple[bool, str, Optional[float]]:
    """
    Test connection to a datasource.

    Returns:
        Tuple of (success, message, response_time_ms)
    """
    start_time = time.time()

    try:
        if datasource_type == "loki":
            client = LokiClient(url=url, timeout=timeout)
            is_healthy = await client.test_connection()
            response_time_ms = (time.time() - start_time) * 1000

            if is_healthy:
                return True, "Loki connection successful", response_time_ms
            else:
                return False, "Loki is not ready", response_time_ms

        elif datasource_type == "tempo":
            client = TempoClient(url=url, timeout=timeout)
            is_healthy = await client.test_connection()
            response_time_ms = (time.time() - start_time) * 1000

            if is_healthy:
                return True, "Tempo connection successful", response_time_ms
            else:
                return False, "Tempo is not ready", response_time_ms

        elif datasource_type in ["prometheus", "mimir"]:
            # Use httpx to test prometheus/mimir ready endpoint
            import httpx
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{url.rstrip('/')}/-/ready")
                response_time_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    return True, f"{datasource_type.capitalize()} connection successful", response_time_ms
                else:
                    return False, f"{datasource_type.capitalize()} returned status {response.status_code}", response_time_ms

        elif datasource_type == "alertmanager":
            # Test alertmanager status endpoint
            import httpx
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{url.rstrip('/')}/-/ready")
                response_time_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    return True, "Alertmanager connection successful", response_time_ms
                else:
                    return False, f"Alertmanager returned status {response.status_code}", response_time_ms

        else:
            return False, f"Datasource type '{datasource_type}' not supported for connection testing", None

    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        return False, f"Connection failed: {str(e)}", response_time_ms


# ============================================================================
# POST /api/grafana-datasources - Create Datasource
# ============================================================================

@router.post("", response_model=GrafanaDatasourceResponse, status_code=status.HTTP_201_CREATED)
async def create_datasource(
    datasource_data: GrafanaDatasourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new Grafana datasource.

    Creates a datasource configuration for Loki, Tempo, Prometheus, or other observability backends.
    If is_default is True, any existing default datasource of the same type will be updated to False.
    """
    # Check if datasource with same name already exists
    existing = db.query(GrafanaDatasource).filter(
        GrafanaDatasource.name == datasource_data.name
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Datasource with name '{datasource_data.name}' already exists"
        )

    # If this datasource is set as default, unset other defaults of same type
    if datasource_data.is_default:
        db.query(GrafanaDatasource).filter(
            GrafanaDatasource.datasource_type == datasource_data.datasource_type,
            GrafanaDatasource.is_default == True
        ).update({"is_default": False})

    # Create datasource
    datasource = GrafanaDatasource(
        name=datasource_data.name,
        datasource_type=datasource_data.datasource_type,
        url=datasource_data.url,
        description=datasource_data.description,
        auth_type=datasource_data.auth_type,
        username=datasource_data.username,
        password=datasource_data.password,  # TODO: Encrypt in production
        bearer_token=datasource_data.bearer_token,  # TODO: Encrypt in production
        timeout=datasource_data.timeout,
        is_default=datasource_data.is_default,
        is_enabled=datasource_data.is_enabled,
        config_json=datasource_data.config_json,
        custom_headers=datasource_data.custom_headers,
        created_by=current_user.username
    )

    db.add(datasource)
    db.commit()
    db.refresh(datasource)

    return datasource


# ============================================================================
# GET /api/grafana-datasources - List Datasources
# ============================================================================

@router.get("", response_model=GrafanaDatasourceListResponse)
async def list_datasources(
    page: int = 1,
    page_size: int = 50,
    datasource_type: Optional[str] = None,
    is_enabled: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all Grafana datasources with pagination and filtering.

    Supports filtering by:
    - datasource_type: Filter by type (loki, tempo, prometheus, etc.)
    - is_enabled: Filter by enabled status
    - search: Search in name and description
    """
    query = db.query(GrafanaDatasource)

    # Apply filters
    if datasource_type:
        query = query.filter(GrafanaDatasource.datasource_type == datasource_type)

    if is_enabled is not None:
        query = query.filter(GrafanaDatasource.is_enabled == is_enabled)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                GrafanaDatasource.name.ilike(search_pattern),
                GrafanaDatasource.description.ilike(search_pattern)
            )
        )

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    datasources = query.order_by(GrafanaDatasource.created_at.desc()).offset(offset).limit(page_size).all()

    return GrafanaDatasourceListResponse(
        items=datasources,
        total=total,
        page=page,
        page_size=page_size
    )


# ============================================================================
# GET /api/grafana-datasources/{datasource_id} - Get Datasource
# ============================================================================

@router.get("/{datasource_id}", response_model=GrafanaDatasourceResponse)
async def get_datasource(
    datasource_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific Grafana datasource by ID."""
    datasource = db.query(GrafanaDatasource).filter(
        GrafanaDatasource.id == datasource_id
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasource with ID {datasource_id} not found"
        )

    return datasource


# ============================================================================
# GET /api/grafana-datasources/type/{datasource_type}/default - Get Default
# ============================================================================

@router.get("/type/{datasource_type}/default", response_model=GrafanaDatasourceResponse)
async def get_default_datasource(
    datasource_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the default datasource for a specific type.

    Returns the datasource marked as default for the given type (loki, tempo, etc.)
    """
    datasource = db.query(GrafanaDatasource).filter(
        GrafanaDatasource.datasource_type == datasource_type,
        GrafanaDatasource.is_default == True,
        GrafanaDatasource.is_enabled == True
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No default datasource found for type '{datasource_type}'"
        )

    return datasource


# ============================================================================
# PUT /api/grafana-datasources/{datasource_id} - Update Datasource
# ============================================================================

@router.put("/{datasource_id}", response_model=GrafanaDatasourceResponse)
async def update_datasource(
    datasource_id: UUID,
    datasource_data: GrafanaDatasourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a Grafana datasource.

    Allows updating configuration, credentials, and settings.
    If is_default is set to True, other defaults of the same type will be unset.
    """
    datasource = db.query(GrafanaDatasource).filter(
        GrafanaDatasource.id == datasource_id
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasource with ID {datasource_id} not found"
        )

    # Check if changing to default
    if datasource_data.is_default and not datasource.is_default:
        # Unset other defaults of same type
        db.query(GrafanaDatasource).filter(
            GrafanaDatasource.datasource_type == datasource.datasource_type,
            GrafanaDatasource.is_default == True,
            GrafanaDatasource.id != datasource_id
        ).update({"is_default": False})

    # Check for name conflicts
    if datasource_data.name and datasource_data.name != datasource.name:
        existing = db.query(GrafanaDatasource).filter(
            GrafanaDatasource.name == datasource_data.name,
            GrafanaDatasource.id != datasource_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Datasource with name '{datasource_data.name}' already exists"
            )

    # Update fields
    update_data = datasource_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(datasource, field, value)

    db.commit()
    db.refresh(datasource)

    return datasource


# ============================================================================
# DELETE /api/grafana-datasources/{datasource_id} - Delete Datasource
# ============================================================================

@router.delete("/{datasource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_datasource(
    datasource_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a Grafana datasource.

    Note: This will fail if any application profiles reference this datasource.
    """
    datasource = db.query(GrafanaDatasource).filter(
        GrafanaDatasource.id == datasource_id
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasource with ID {datasource_id} not found"
        )

    # TODO: Check if any application profiles reference this datasource
    # For now, we'll allow deletion

    db.delete(datasource)
    db.commit()

    return None


# ============================================================================
# GET /api/grafana-datasources/{datasource_id}/health-check - Health Check
# ============================================================================

@router.get("/{datasource_id}/health-check", response_model=DatasourceHealthCheckResponse)
async def check_datasource_health(
    datasource_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Perform health check on a datasource.

    Tests the connection and updates the datasource's health status.
    """
    datasource = db.query(GrafanaDatasource).filter(
        GrafanaDatasource.id == datasource_id
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasource with ID {datasource_id} not found"
        )

    # Perform health check
    is_healthy, message, response_time_ms = await test_datasource_connection(
        datasource_type=datasource.datasource_type,
        url=datasource.url,
        timeout=datasource.timeout,
        auth_type=datasource.auth_type,
        username=datasource.username,
        password=datasource.password,
        bearer_token=datasource.bearer_token
    )

    # Update datasource health status
    datasource.is_healthy = is_healthy
    datasource.health_message = message
    datasource.last_health_check = datetime.now(timezone.utc)
    db.commit()

    return DatasourceHealthCheckResponse(
        datasource_id=datasource.id,
        datasource_name=datasource.name,
        datasource_type=datasource.datasource_type,
        is_healthy=is_healthy,
        response_time_ms=response_time_ms,
        message=message,
        checked_at=datasource.last_health_check
    )


# ============================================================================
# POST /api/grafana-datasources/test-connection - Test Connection
# ============================================================================

@router.post("/test-connection", response_model=DatasourceTestConnectionResponse)
async def test_connection(
    test_request: DatasourceTestConnectionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Test connection to a datasource before creating it.

    Validates the connection parameters without saving to the database.
    """
    success, message, response_time_ms = await test_datasource_connection(
        datasource_type=test_request.datasource_type,
        url=test_request.url,
        timeout=test_request.timeout,
        auth_type=test_request.auth_type,
        username=test_request.username,
        password=test_request.password,
        bearer_token=test_request.bearer_token
    )

    return DatasourceTestConnectionResponse(
        success=success,
        message=message,
        response_time_ms=response_time_ms,
        details={"datasource_type": test_request.datasource_type}
    )
