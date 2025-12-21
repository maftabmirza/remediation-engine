"""
Dashboard Management API
Provides CRUD operations for managing dashboards and their panels
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
import uuid

from app.database import get_db
from app.models_dashboards import Dashboard, DashboardPanel, PrometheusPanel, PrometheusDatasource
from app.auth import get_current_user

router = APIRouter(prefix="/api/dashboards", tags=["Dashboards"])


# Pydantic schemas
class DashboardBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    layout: Optional[Dict[str, Any]] = None
    time_range: str = Field(default="24h")
    refresh_interval: int = Field(default=60, ge=5, le=3600)
    auto_refresh: bool = True
    tags: Optional[List[str]] = None
    folder: Optional[str] = None
    is_public: bool = False
    is_favorite: bool = False
    is_home: bool = False


class DashboardCreate(DashboardBase):
    pass


class DashboardUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    layout: Optional[Dict[str, Any]] = None
    time_range: Optional[str] = None
    refresh_interval: Optional[int] = Field(None, ge=5, le=3600)
    auto_refresh: Optional[bool] = None
    tags: Optional[List[str]] = None
    folder: Optional[str] = None
    is_public: Optional[bool] = None
    is_favorite: Optional[bool] = None
    is_home: Optional[bool] = None


class DashboardPanelInfo(BaseModel):
    panel_id: str
    panel_name: str
    panel_type: str
    grid_x: int
    grid_y: int
    grid_width: int
    grid_height: int
    override_time_range: Optional[str]
    override_refresh_interval: Optional[int]
    display_order: int

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    layout: Optional[Dict[str, Any]]
    time_range: str
    refresh_interval: int
    auto_refresh: bool
    tags: Optional[List[str]]
    folder: Optional[str]
    is_public: bool
    is_favorite: bool
    is_home: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    panel_count: Optional[int] = None

    class Config:
        from_attributes = True


class DashboardDetailResponse(DashboardResponse):
    panels: List[DashboardPanelInfo]


class AddPanelRequest(BaseModel):
    panel_id: str
    grid_x: int = Field(default=0, ge=0, le=23)
    grid_y: int = Field(default=0, ge=0)
    grid_width: int = Field(default=6, ge=1, le=24)
    grid_height: int = Field(default=4, ge=1, le=24)
    override_time_range: Optional[str] = None
    override_refresh_interval: Optional[int] = None
    display_order: Optional[int] = None


class UpdatePanelPositionRequest(BaseModel):
    grid_x: Optional[int] = Field(None, ge=0, le=23)
    grid_y: Optional[int] = Field(None, ge=0)
    grid_width: Optional[int] = Field(None, ge=1, le=24)
    grid_height: Optional[int] = Field(None, ge=1, le=24)
    override_time_range: Optional[str] = None
    override_refresh_interval: Optional[int] = None
    display_order: Optional[int] = None


# API Endpoints
@router.get("/", response_model=List[DashboardResponse])
async def list_dashboards(
    tag: Optional[str] = Query(None, description="Filter by tag"),
    folder: Optional[str] = Query(None, description="Filter by folder"),
    favorites_only: bool = Query(False, description="Show favorites only"),
    search: Optional[str] = Query(None, description="Search in name or description"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    List dashboards with optional filtering

    - **tag**: Filter by tag
    - **folder**: Filter by folder
    - **favorites_only**: Show only favorite dashboards
    - **search**: Search in name or description
    """
    query = db.query(Dashboard)

    # Apply filters
    if folder:
        query = query.filter(Dashboard.folder == folder)

    if favorites_only:
        query = query.filter(Dashboard.is_favorite == True)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Dashboard.name.ilike(search_pattern)) |
            (Dashboard.description.ilike(search_pattern))
        )

    if tag:
        query = query.filter(Dashboard.tags.contains([tag]))

    # Order and paginate
    dashboards = query.order_by(
        Dashboard.is_home.desc(),
        Dashboard.is_favorite.desc(),
        Dashboard.updated_at.desc()
    ).limit(limit).offset(offset).all()

    # Add panel count
    result = []
    for dashboard in dashboards:
        dash_dict = {
            "id": dashboard.id,
            "name": dashboard.name,
            "description": dashboard.description,
            "layout": dashboard.layout,
            "time_range": dashboard.time_range,
            "refresh_interval": dashboard.refresh_interval,
            "auto_refresh": dashboard.auto_refresh,
            "tags": dashboard.tags,
            "folder": dashboard.folder,
            "is_public": dashboard.is_public,
            "is_favorite": dashboard.is_favorite,
            "is_home": dashboard.is_home,
            "created_at": dashboard.created_at,
            "updated_at": dashboard.updated_at,
            "created_by": dashboard.created_by,
            "panel_count": len(dashboard.panels)
        }
        result.append(DashboardResponse(**dash_dict))

    return result


@router.get("/{dashboard_id}", response_model=DashboardDetailResponse)
async def get_dashboard(
    dashboard_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a dashboard with all its panels"""
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id
    ).first()

    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found"
        )

    # Build response with panels
    panel_infos = []
    for dp in dashboard.panels:
        panel = db.query(PrometheusPanel).filter(
            PrometheusPanel.id == dp.panel_id
        ).first()

        if panel:
            panel_infos.append(DashboardPanelInfo(
                panel_id=dp.panel_id,
                panel_name=panel.name,
                panel_type=panel.panel_type.value,
                grid_x=dp.grid_x,
                grid_y=dp.grid_y,
                grid_width=dp.grid_width,
                grid_height=dp.grid_height,
                override_time_range=dp.override_time_range,
                override_refresh_interval=dp.override_refresh_interval,
                display_order=dp.display_order
            ))

    # Sort by display order
    panel_infos.sort(key=lambda p: p.display_order)

    return DashboardDetailResponse(
        id=dashboard.id,
        name=dashboard.name,
        description=dashboard.description,
        layout=dashboard.layout,
        time_range=dashboard.time_range,
        refresh_interval=dashboard.refresh_interval,
        auto_refresh=dashboard.auto_refresh,
        tags=dashboard.tags,
        folder=dashboard.folder,
        is_public=dashboard.is_public,
        is_favorite=dashboard.is_favorite,
        is_home=dashboard.is_home,
        created_at=dashboard.created_at,
        updated_at=dashboard.updated_at,
        created_by=dashboard.created_by,
        panel_count=len(panel_infos),
        panels=panel_infos
    )


@router.post("/", response_model=DashboardResponse, status_code=status.HTTP_201_CREATED)
async def create_dashboard(
    dashboard: DashboardCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new dashboard

    - **name**: Dashboard name
    - **time_range**: Default time range for all panels
    - **refresh_interval**: Auto-refresh interval in seconds
    - **tags**: Tags for organization
    """
    # If setting as home, unset other home dashboards
    if dashboard.is_home:
        db.query(Dashboard).update({"is_home": False})

    # Create dashboard
    new_dashboard = Dashboard(
        id=str(uuid.uuid4()),
        name=dashboard.name,
        description=dashboard.description,
        layout=dashboard.layout,
        time_range=dashboard.time_range,
        refresh_interval=dashboard.refresh_interval,
        auto_refresh=dashboard.auto_refresh,
        tags=dashboard.tags,
        folder=dashboard.folder,
        is_public=dashboard.is_public,
        is_favorite=dashboard.is_favorite,
        is_home=dashboard.is_home,
        created_by=current_user.get("username")
    )

    db.add(new_dashboard)
    db.commit()
    db.refresh(new_dashboard)

    return DashboardResponse(
        **{
            "id": new_dashboard.id,
            "name": new_dashboard.name,
            "description": new_dashboard.description,
            "layout": new_dashboard.layout,
            "time_range": new_dashboard.time_range,
            "refresh_interval": new_dashboard.refresh_interval,
            "auto_refresh": new_dashboard.auto_refresh,
            "tags": new_dashboard.tags,
            "folder": new_dashboard.folder,
            "is_public": new_dashboard.is_public,
            "is_favorite": new_dashboard.is_favorite,
            "is_home": new_dashboard.is_home,
            "created_at": new_dashboard.created_at,
            "updated_at": new_dashboard.updated_at,
            "created_by": new_dashboard.created_by,
            "panel_count": 0
        }
    )


@router.put("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: str,
    dashboard_update: DashboardUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update an existing dashboard"""
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id
    ).first()

    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found"
        )

    # If setting as home, unset other home dashboards
    if dashboard_update.is_home:
        db.query(Dashboard).filter(
            Dashboard.id != dashboard_id
        ).update({"is_home": False})

    # Update fields
    update_data = dashboard_update.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()

    for key, value in update_data.items():
        setattr(dashboard, key, value)

    db.commit()
    db.refresh(dashboard)

    return DashboardResponse(
        **{
            "id": dashboard.id,
            "name": dashboard.name,
            "description": dashboard.description,
            "layout": dashboard.layout,
            "time_range": dashboard.time_range,
            "refresh_interval": dashboard.refresh_interval,
            "auto_refresh": dashboard.auto_refresh,
            "tags": dashboard.tags,
            "folder": dashboard.folder,
            "is_public": dashboard.is_public,
            "is_favorite": dashboard.is_favorite,
            "is_home": dashboard.is_home,
            "created_at": dashboard.created_at,
            "updated_at": dashboard.updated_at,
            "created_by": dashboard.created_by,
            "panel_count": len(dashboard.panels)
        }
    )


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(
    dashboard_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a dashboard"""
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id
    ).first()

    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found"
        )

    db.delete(dashboard)
    db.commit()

    return None


@router.post("/{dashboard_id}/panels", status_code=status.HTTP_201_CREATED)
async def add_panel_to_dashboard(
    dashboard_id: str,
    request: AddPanelRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Add a panel to a dashboard

    - **panel_id**: ID of the panel to add
    - **grid_x**: X position in grid (0-23)
    - **grid_y**: Y position in grid
    - **grid_width**: Width in grid units (1-24)
    - **grid_height**: Height in grid units
    """
    # Verify dashboard exists
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id
    ).first()

    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found"
        )

    # Verify panel exists
    panel = db.query(PrometheusPanel).filter(
        PrometheusPanel.id == request.panel_id
    ).first()

    if not panel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Panel {request.panel_id} not found"
        )

    # Check if panel already in dashboard
    existing = db.query(DashboardPanel).filter(
        DashboardPanel.dashboard_id == dashboard_id,
        DashboardPanel.panel_id == request.panel_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Panel {request.panel_id} already in dashboard"
        )

    # Calculate display order if not provided
    if request.display_order is None:
        max_order = db.query(DashboardPanel).filter(
            DashboardPanel.dashboard_id == dashboard_id
        ).count()
        display_order = max_order
    else:
        display_order = request.display_order

    # Add panel to dashboard
    dashboard_panel = DashboardPanel(
        id=str(uuid.uuid4()),
        dashboard_id=dashboard_id,
        panel_id=request.panel_id,
        grid_x=request.grid_x,
        grid_y=request.grid_y,
        grid_width=request.grid_width,
        grid_height=request.grid_height,
        override_time_range=request.override_time_range,
        override_refresh_interval=request.override_refresh_interval,
        display_order=display_order
    )

    db.add(dashboard_panel)

    # Update dashboard timestamp
    dashboard.updated_at = datetime.utcnow()

    db.commit()

    return {"message": "Panel added to dashboard", "dashboard_id": dashboard_id, "panel_id": request.panel_id}


@router.delete("/{dashboard_id}/panels/{panel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_panel_from_dashboard(
    dashboard_id: str,
    panel_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Remove a panel from a dashboard"""
    dashboard_panel = db.query(DashboardPanel).filter(
        DashboardPanel.dashboard_id == dashboard_id,
        DashboardPanel.panel_id == panel_id
    ).first()

    if not dashboard_panel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Panel {panel_id} not found in dashboard {dashboard_id}"
        )

    db.delete(dashboard_panel)

    # Update dashboard timestamp
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if dashboard:
        dashboard.updated_at = datetime.utcnow()

    db.commit()

    return None


@router.put("/{dashboard_id}/panels/{panel_id}/position")
async def update_panel_position(
    dashboard_id: str,
    panel_id: str,
    request: UpdatePanelPositionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update panel position and size in dashboard

    - **grid_x**: X position in grid
    - **grid_y**: Y position in grid
    - **grid_width**: Width in grid units
    - **grid_height**: Height in grid units
    """
    dashboard_panel = db.query(DashboardPanel).filter(
        DashboardPanel.dashboard_id == dashboard_id,
        DashboardPanel.panel_id == panel_id
    ).first()

    if not dashboard_panel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Panel {panel_id} not found in dashboard {dashboard_id}"
        )

    # Update position/size
    update_data = request.dict(exclude_unset=True)

    for key, value in update_data.items():
        setattr(dashboard_panel, key, value)

    # Update dashboard timestamp
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if dashboard:
        dashboard.updated_at = datetime.utcnow()

    db.commit()

    return {"message": "Panel position updated", "dashboard_id": dashboard_id, "panel_id": panel_id}


@router.post("/{dashboard_id}/clone", response_model=DashboardResponse)
async def clone_dashboard(
    dashboard_id: str,
    new_name: Optional[str] = Query(None, description="Name for cloned dashboard"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Clone a dashboard with all its panels

    Creates a copy of the dashboard and all panel associations
    """
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id
    ).first()

    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dashboard {dashboard_id} not found"
        )

    # Create cloned dashboard
    cloned_dashboard = Dashboard(
        id=str(uuid.uuid4()),
        name=new_name or f"{dashboard.name} (Copy)",
        description=dashboard.description,
        layout=dashboard.layout,
        time_range=dashboard.time_range,
        refresh_interval=dashboard.refresh_interval,
        auto_refresh=dashboard.auto_refresh,
        tags=dashboard.tags,
        folder=dashboard.folder,
        is_public=dashboard.is_public,
        is_favorite=False,  # Clones are not favorites
        is_home=False,  # Clones are not home
        created_by=current_user.get("username")
    )

    db.add(cloned_dashboard)
    db.flush()  # Get the ID

    # Clone all panel associations
    for dp in dashboard.panels:
        cloned_panel_assoc = DashboardPanel(
            id=str(uuid.uuid4()),
            dashboard_id=cloned_dashboard.id,
            panel_id=dp.panel_id,
            grid_x=dp.grid_x,
            grid_y=dp.grid_y,
            grid_width=dp.grid_width,
            grid_height=dp.grid_height,
            override_time_range=dp.override_time_range,
            override_refresh_interval=dp.override_refresh_interval,
            display_order=dp.display_order
        )
        db.add(cloned_panel_assoc)

    db.commit()
    db.refresh(cloned_dashboard)

    return DashboardResponse(
        **{
            "id": cloned_dashboard.id,
            "name": cloned_dashboard.name,
            "description": cloned_dashboard.description,
            "layout": cloned_dashboard.layout,
            "time_range": cloned_dashboard.time_range,
            "refresh_interval": cloned_dashboard.refresh_interval,
            "auto_refresh": cloned_dashboard.auto_refresh,
            "tags": cloned_dashboard.tags,
            "folder": cloned_dashboard.folder,
            "is_public": cloned_dashboard.is_public,
            "is_favorite": cloned_dashboard.is_favorite,
            "is_home": cloned_dashboard.is_home,
            "created_at": cloned_dashboard.created_at,
            "updated_at": cloned_dashboard.updated_at,
            "created_by": cloned_dashboard.created_by,
            "panel_count": len(cloned_dashboard.panels)
        }
    )


@router.get("/folders/list", response_model=List[str])
async def list_folders(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get list of all folders"""
    folders = db.query(Dashboard.folder).filter(
        Dashboard.folder.isnot(None)
    ).distinct().all()

    return [f[0] for f in folders if f[0]]


@router.get("/home/get", response_model=DashboardDetailResponse)
async def get_home_dashboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get the home dashboard"""
    dashboard = db.query(Dashboard).filter(
        Dashboard.is_home == True
    ).first()

    if not dashboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No home dashboard configured"
        )

    # Build response with panels
    panel_infos = []
    for dp in dashboard.panels:
        panel = db.query(PrometheusPanel).filter(
            PrometheusPanel.id == dp.panel_id
        ).first()

        if panel:
            panel_infos.append(DashboardPanelInfo(
                panel_id=dp.panel_id,
                panel_name=panel.name,
                panel_type=panel.panel_type.value,
                grid_x=dp.grid_x,
                grid_y=dp.grid_y,
                grid_width=dp.grid_width,
                grid_height=dp.grid_height,
                override_time_range=dp.override_time_range,
                override_refresh_interval=dp.override_refresh_interval,
                display_order=dp.display_order
            ))

    panel_infos.sort(key=lambda p: p.display_order)

    return DashboardDetailResponse(
        id=dashboard.id,
        name=dashboard.name,
        description=dashboard.description,
        layout=dashboard.layout,
        time_range=dashboard.time_range,
        refresh_interval=dashboard.refresh_interval,
        auto_refresh=dashboard.auto_refresh,
        tags=dashboard.tags,
        folder=dashboard.folder,
        is_public=dashboard.is_public,
        is_favorite=dashboard.is_favorite,
        is_home=dashboard.is_home,
        created_at=dashboard.created_at,
        updated_at=dashboard.updated_at,
        created_by=dashboard.created_by,
        panel_count=len(panel_infos),
        panels=panel_infos
    )
