"""
Prometheus Panel Management API
Provides CRUD operations for managing saved panels and executing PromQL queries
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timedelta
import httpx
import uuid

from app.database import get_db
from app.models_dashboards import PrometheusPanel, PrometheusDatasource, PanelType
from app.routers.auth import get_current_user
from app.routers.datasources_api import decrypt_password

router = APIRouter(prefix="/api/panels", tags=["Panels"])


# Pydantic schemas
class PanelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    datasource_id: str
    promql_query: str = Field(..., min_length=1)
    legend_format: Optional[str] = None
    time_range: str = Field(default="24h")
    refresh_interval: int = Field(default=30, ge=5, le=3600)
    step: str = Field(default="auto")
    panel_type: PanelType = PanelType.GRAPH
    visualization_config: Optional[Dict[str, Any]] = None
    thresholds: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_public: bool = False
    is_template: bool = False

    @field_validator('time_range')
    @classmethod
    def validate_time_range(cls, v):
        valid_ranges = ['5m', '15m', '30m', '1h', '3h', '6h', '12h', '24h', '7d', '30d', '90d']
        if v not in valid_ranges:
            raise ValueError(f'time_range must be one of: {", ".join(valid_ranges)}')
        return v


class PanelCreate(PanelBase):
    pass


class PanelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    datasource_id: Optional[str] = None
    promql_query: Optional[str] = Field(None, min_length=1)
    legend_format: Optional[str] = None
    time_range: Optional[str] = None
    refresh_interval: Optional[int] = Field(None, ge=5, le=3600)
    step: Optional[str] = None
    panel_type: Optional[PanelType] = None
    visualization_config: Optional[Dict[str, Any]] = None
    thresholds: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    is_template: Optional[bool] = None


class PanelResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    datasource_id: str
    promql_query: str
    legend_format: Optional[str]
    time_range: str
    refresh_interval: int
    step: str
    panel_type: PanelType
    visualization_config: Optional[Dict[str, Any]]
    thresholds: Optional[Dict[str, Any]]
    tags: Optional[List[str]]
    is_public: bool
    is_template: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


class QueryTestRequest(BaseModel):
    datasource_id: str
    promql_query: str
    time_range: Optional[str] = "1h"


class QueryTestResponse(BaseModel):
    valid: bool
    message: str
    result_type: Optional[str] = None
    series_count: Optional[int] = None
    sample_data: Optional[List[Dict[str, Any]]] = None


class PanelDataRequest(BaseModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    step: Optional[str] = None


class PanelDataResponse(BaseModel):
    panel_id: str
    panel_name: str
    query: str
    result_type: str
    data: List[Dict[str, Any]]
    metadata: Dict[str, Any]


# Helper functions
def parse_time_range(time_range: str) -> timedelta:
    """Convert time range string to timedelta"""
    mappings = {
        '5m': timedelta(minutes=5),
        '15m': timedelta(minutes=15),
        '30m': timedelta(minutes=30),
        '1h': timedelta(hours=1),
        '3h': timedelta(hours=3),
        '6h': timedelta(hours=6),
        '12h': timedelta(hours=12),
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
        '90d': timedelta(days=90),
    }
    return mappings.get(time_range, timedelta(hours=24))


def calculate_step(duration: timedelta, max_points: int = 1000) -> str:
    """Calculate appropriate step interval based on duration"""
    total_seconds = duration.total_seconds()
    step_seconds = max(15, int(total_seconds / max_points))

    if step_seconds < 60:
        return f"{step_seconds}s"
    elif step_seconds < 3600:
        return f"{step_seconds // 60}m"
    else:
        return f"{step_seconds // 3600}h"


async def execute_prometheus_query(
    datasource: PrometheusDatasource,
    query: str,
    start: datetime,
    end: datetime,
    step: str
) -> Dict[str, Any]:
    """Execute a PromQL query against a datasource"""
    # Build auth
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

    # Execute query
    async with httpx.AsyncClient(timeout=datasource.timeout) as client:
        try:
            response = await client.get(
                f"{datasource.url}/api/v1/query_range",
                params={
                    "query": query,
                    "start": start.timestamp(),
                    "end": end.timestamp(),
                    "step": step
                },
                headers=headers,
                auth=auth
            )

            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Prometheus returned HTTP {response.status_code}: {response.text}"
                )

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Prometheus query timeout after {datasource.timeout}s"
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Cannot connect to Prometheus at {datasource.url}"
            )


# API Endpoints
@router.get("/", response_model=List[PanelResponse])
async def list_panels(
    tag: Optional[str] = Query(None, description="Filter by tag"),
    panel_type: Optional[PanelType] = Query(None, description="Filter by panel type"),
    datasource_id: Optional[str] = Query(None, description="Filter by datasource"),
    is_template: Optional[bool] = Query(None, description="Filter templates only"),
    search: Optional[str] = Query(None, description="Search in name or description"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    List panels with optional filtering

    - **tag**: Filter by tag
    - **panel_type**: Filter by visualization type
    - **datasource_id**: Filter by datasource
    - **is_template**: Show only templates
    - **search**: Search in name or description
    """
    query = db.query(PrometheusPanel)

    # Apply filters
    if panel_type:
        query = query.filter(PrometheusPanel.panel_type == panel_type)

    if datasource_id:
        query = query.filter(PrometheusPanel.datasource_id == datasource_id)

    if is_template is not None:
        query = query.filter(PrometheusPanel.is_template == is_template)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (PrometheusPanel.name.ilike(search_pattern)) |
            (PrometheusPanel.description.ilike(search_pattern))
        )

    if tag:
        # Filter by tag in JSON array
        query = query.filter(PrometheusPanel.tags.contains([tag]))

    # Order and paginate
    panels = query.order_by(
        PrometheusPanel.is_template.desc(),
        PrometheusPanel.created_at.desc()
    ).limit(limit).offset(offset).all()

    return panels


@router.get("/{panel_id}", response_model=PanelResponse)
async def get_panel(
    panel_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific panel by ID"""
    panel = db.query(PrometheusPanel).filter(
        PrometheusPanel.id == panel_id
    ).first()

    if not panel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Panel {panel_id} not found"
        )

    return panel


@router.post("/", response_model=PanelResponse, status_code=status.HTTP_201_CREATED)
async def create_panel(
    panel: PanelCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new panel with PromQL query

    - **name**: Panel name
    - **datasource_id**: Which Prometheus to query
    - **promql_query**: Custom PromQL query
    - **panel_type**: Visualization type (graph, gauge, stat, etc.)
    - **tags**: Tags for organization
    """
    # Verify datasource exists
    datasource = db.query(PrometheusDatasource).filter(
        PrometheusDatasource.id == panel.datasource_id
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasource {panel.datasource_id} not found"
        )

    # Create panel
    new_panel = PrometheusPanel(
        id=str(uuid.uuid4()),
        name=panel.name,
        description=panel.description,
        datasource_id=panel.datasource_id,
        promql_query=panel.promql_query,
        legend_format=panel.legend_format,
        time_range=panel.time_range,
        refresh_interval=panel.refresh_interval,
        step=panel.step,
        panel_type=panel.panel_type.value if hasattr(panel.panel_type, 'value') else panel.panel_type,
        visualization_config=panel.visualization_config,
        thresholds=panel.thresholds,
        tags=panel.tags,
        is_public=panel.is_public,
        is_template=panel.is_template,
        created_by=current_user.username
    )

    db.add(new_panel)
    db.commit()
    db.refresh(new_panel)

    return new_panel


@router.put("/{panel_id}", response_model=PanelResponse)
async def update_panel(
    panel_id: str,
    panel_update: PanelUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update an existing panel"""
    panel = db.query(PrometheusPanel).filter(
        PrometheusPanel.id == panel_id
    ).first()

    if not panel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Panel {panel_id} not found"
        )

    # Verify datasource if being changed
    if panel_update.datasource_id:
        datasource = db.query(PrometheusDatasource).filter(
            PrometheusDatasource.id == panel_update.datasource_id
        ).first()
        if not datasource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Datasource {panel_update.datasource_id} not found"
            )

    # Update fields
    update_data = panel_update.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()

    for key, value in update_data.items():
        setattr(panel, key, value)

    db.commit()
    db.refresh(panel)

    return panel


@router.delete("/{panel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_panel(
    panel_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a panel"""
    panel = db.query(PrometheusPanel).filter(
        PrometheusPanel.id == panel_id
    ).first()

    if not panel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Panel {panel_id} not found"
        )

    db.delete(panel)
    db.commit()

    return None


@router.post("/test-query", response_model=QueryTestResponse)
async def test_query(
    request: QueryTestRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Test a PromQL query without saving it

    Returns validation status and sample data
    """
    # Get datasource
    datasource = db.query(PrometheusDatasource).filter(
        PrometheusDatasource.id == request.datasource_id
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasource {request.datasource_id} not found"
        )

    # Build auth
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

    # Execute test query (instant query for speed)
    async with httpx.AsyncClient(timeout=datasource.timeout) as client:
        try:
            response = await client.get(
                f"{datasource.url}/api/v1/query",
                params={"query": request.promql_query},
                headers=headers,
                auth=auth
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("status") == "success":
                    result = data.get("data", {}).get("result", [])
                    result_type = data.get("data", {}).get("resultType", "unknown")

                    # Sample data (first 5 series)
                    sample = result[:5] if len(result) > 5 else result

                    return QueryTestResponse(
                        valid=True,
                        message=f"Query valid, returned {len(result)} series",
                        result_type=result_type,
                        series_count=len(result),
                        sample_data=sample
                    )
                else:
                    error_msg = data.get("error", "Unknown error")
                    return QueryTestResponse(
                        valid=False,
                        message=f"Query error: {error_msg}"
                    )
            else:
                return QueryTestResponse(
                    valid=False,
                    message=f"HTTP {response.status_code}: {response.text}"
                )

        except httpx.TimeoutException:
            return QueryTestResponse(
                valid=False,
                message=f"Query timeout after {datasource.timeout}s"
            )
        except httpx.ConnectError:
            return QueryTestResponse(
                valid=False,
                message=f"Cannot connect to {datasource.url}"
            )
        except Exception as e:
            return QueryTestResponse(
                valid=False,
                message=f"Error: {str(e)}"
            )


@router.get("/{panel_id}/data", response_model=PanelDataResponse)
async def get_panel_data(
    panel_id: str,
    start: Optional[datetime] = Query(None, description="Start time (ISO format)"),
    end: Optional[datetime] = Query(None, description="End time (ISO format)"),
    step: Optional[str] = Query(None, description="Step interval (e.g., 15s, 1m, 5m)"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get data for a panel by executing its PromQL query

    - **start**: Start time (defaults to now - time_range)
    - **end**: End time (defaults to now)
    - **step**: Step interval (defaults to auto-calculated)
    """
    # Get panel
    panel = db.query(PrometheusPanel).filter(
        PrometheusPanel.id == panel_id
    ).first()

    if not panel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Panel {panel_id} not found"
        )

    # Get datasource
    datasource = db.query(PrometheusDatasource).filter(
        PrometheusDatasource.id == panel.datasource_id
    ).first()

    if not datasource:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasource {panel.datasource_id} not found"
        )

    # Calculate time range
    if not end:
        end = datetime.utcnow()
    if not start:
        duration = parse_time_range(panel.time_range)
        start = end - duration
    else:
        duration = end - start

    # Calculate step
    if not step:
        if panel.step == "auto":
            step = calculate_step(duration)
        else:
            step = panel.step

    # Execute query
    result = await execute_prometheus_query(
        datasource, panel.promql_query, start, end, step
    )

    # Extract data
    data = result.get("data", {})
    result_type = data.get("resultType", "unknown")
    series = data.get("result", [])

    return PanelDataResponse(
        panel_id=panel_id,
        panel_name=panel.name,
        query=panel.promql_query,
        result_type=result_type,
        data=series,
        metadata={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "step": step,
            "series_count": len(series),
            "datasource": datasource.name
        }
    )


@router.post("/{panel_id}/clone", response_model=PanelResponse)
async def clone_panel(
    panel_id: str,
    new_name: Optional[str] = Query(None, description="Name for cloned panel"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Clone an existing panel"""
    panel = db.query(PrometheusPanel).filter(
        PrometheusPanel.id == panel_id
    ).first()

    if not panel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Panel {panel_id} not found"
        )

    # Create clone
    cloned_panel = PrometheusPanel(
        id=str(uuid.uuid4()),
        name=new_name or f"{panel.name} (Copy)",
        description=panel.description,
        datasource_id=panel.datasource_id,
        promql_query=panel.promql_query,
        legend_format=panel.legend_format,
        time_range=panel.time_range,
        refresh_interval=panel.refresh_interval,
        step=panel.step,
        panel_type=panel.panel_type,
        visualization_config=panel.visualization_config,
        thresholds=panel.thresholds,
        tags=panel.tags,
        is_public=panel.is_public,
        is_template=False,  # Clones are not templates
        created_by=current_user.username
    )

    db.add(cloned_panel)
    db.commit()
    db.refresh(cloned_panel)

    return cloned_panel
