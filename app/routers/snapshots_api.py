"""
Dashboard Snapshots API

API endpoints for creating, viewing, and managing dashboard snapshots.
Snapshots are frozen, shareable copies of dashboards.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import uuid
import secrets

from app.database import get_db
from app.models_dashboards import (
    Dashboard, DashboardSnapshot, DashboardPanel, PrometheusPanel,
    DashboardVariable, DashboardAnnotation
)

router = APIRouter(
    prefix="/api/snapshots",
    tags=["snapshots"]
)


# Pydantic schemas
class SnapshotCreate(BaseModel):
    name: str
    expires_days: Optional[int] = None  # None = never expires


class SnapshotResponse(BaseModel):
    id: str
    dashboard_id: str
    name: str
    key: str
    is_public: bool
    expires_at: Optional[datetime]
    created_at: datetime
    created_by: Optional[str]
    share_url: str

    class Config:
        from_attributes = True


@router.post("", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    dashboard_id: str,
    snapshot_data: SnapshotCreate,
    db: Session = Depends(get_db)
):
    """
    Create a snapshot of a dashboard.

    Captures the current state of the dashboard including all panels,
    variables, and annotations as a frozen, shareable copy.
    """
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    # Build snapshot data (same as export)
    dashboard_panels = db.query(DashboardPanel).filter(
        DashboardPanel.dashboard_id == dashboard_id
    ).all()

    panels_data = []
    for dp in dashboard_panels:
        panel = db.query(PrometheusPanel).filter(PrometheusPanel.id == dp.panel_id).first()
        if panel:
            panels_data.append({
                "panel": {
                    "name": panel.name,
                    "description": panel.description,
                    "promql_query": panel.promql_query,
                    "legend_format": panel.legend_format,
                    "time_range": panel.time_range,
                    "refresh_interval": panel.refresh_interval,
                    "step": panel.step,
                    "panel_type": panel.panel_type,
                    "visualization_config": panel.visualization_config,
                    "thresholds": panel.thresholds,
                    "tags": panel.tags,
                    "datasource_name": panel.datasource.name if panel.datasource else None
                },
                "position": {
                    "grid_x": dp.grid_x,
                    "grid_y": dp.grid_y,
                    "grid_width": dp.grid_width,
                    "grid_height": dp.grid_height,
                    "display_order": dp.display_order
                }
            })

    # Get variables
    variables = db.query(DashboardVariable).filter(
        DashboardVariable.dashboard_id == dashboard_id
    ).all()

    variables_data = []
    for var in variables:
        variables_data.append({
            "name": var.name,
            "label": var.label,
            "type": var.type,
            "query": var.query,
            "datasource_name": var.datasource.name if var.datasource else None,
            "regex": var.regex,
            "custom_values": var.custom_values,
            "default_value": var.default_value,
            "current_value": var.current_value
        })

    # Get annotations
    annotations = db.query(DashboardAnnotation).filter(
        DashboardAnnotation.dashboard_id == dashboard_id
    ).all()

    annotations_data = []
    for ann in annotations:
        annotations_data.append({
            "time": ann.time.isoformat() if ann.time else None,
            "time_end": ann.time_end.isoformat() if ann.time_end else None,
            "text": ann.text,
            "title": ann.title,
            "tags": ann.tags,
            "color": ann.color
        })

    # Build complete snapshot data
    snapshot_json = {
        "dashboard": {
            "name": dashboard.name,
            "description": dashboard.description,
            "time_range": dashboard.time_range,
            "refresh_interval": dashboard.refresh_interval,
            "tags": dashboard.tags
        },
        "panels": panels_data,
        "variables": variables_data,
        "annotations": annotations_data,
        "snapshot_version": "1.0",
        "snapshot_timestamp": datetime.utcnow().isoformat()
    }

    # Calculate expiration
    expires_at = None
    if snapshot_data.expires_days:
        expires_at = datetime.utcnow() + timedelta(days=snapshot_data.expires_days)

    # Generate unique shareable key
    share_key = secrets.token_urlsafe(32)[:32]

    # Create snapshot
    new_snapshot = DashboardSnapshot(
        id=str(uuid.uuid4()),
        dashboard_id=dashboard_id,
        name=snapshot_data.name,
        key=share_key,
        snapshot_data=snapshot_json,
        is_public=True,
        expires_at=expires_at
    )

    db.add(new_snapshot)
    db.commit()
    db.refresh(new_snapshot)

    return SnapshotResponse(
        id=new_snapshot.id,
        dashboard_id=new_snapshot.dashboard_id,
        name=new_snapshot.name,
        key=new_snapshot.key,
        is_public=new_snapshot.is_public,
        expires_at=new_snapshot.expires_at,
        created_at=new_snapshot.created_at,
        created_by=new_snapshot.created_by,
        share_url=f"/snapshots/{new_snapshot.key}"
    )


@router.get("/{snapshot_key}")
async def get_snapshot(
    snapshot_key: str,
    db: Session = Depends(get_db)
):
    """
    Get a snapshot by its shareable key.

    Returns the complete frozen dashboard data. No authentication required.
    """
    snapshot = db.query(DashboardSnapshot).filter(DashboardSnapshot.key == snapshot_key).first()

    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Check if expired
    if snapshot.expires_at and snapshot.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Snapshot has expired")

    return {
        "id": snapshot.id,
        "name": snapshot.name,
        "key": snapshot.key,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "expires_at": snapshot.expires_at.isoformat() if snapshot.expires_at else None,
        "data": snapshot.snapshot_data
    }


@router.get("/dashboard/{dashboard_id}/list", response_model=List[SnapshotResponse])
async def list_dashboard_snapshots(
    dashboard_id: str,
    db: Session = Depends(get_db)
):
    """List all snapshots for a dashboard."""
    snapshots = db.query(DashboardSnapshot).filter(
        DashboardSnapshot.dashboard_id == dashboard_id
    ).order_by(DashboardSnapshot.created_at.desc()).all()

    return [
        SnapshotResponse(
            id=s.id,
            dashboard_id=s.dashboard_id,
            name=s.name,
            key=s.key,
            is_public=s.is_public,
            expires_at=s.expires_at,
            created_at=s.created_at,
            created_by=s.created_by,
            share_url=f"/snapshots/{s.key}"
        )
        for s in snapshots
    ]


@router.delete("/{snapshot_id}")
async def delete_snapshot(
    snapshot_id: str,
    db: Session = Depends(get_db)
):
    """Delete a snapshot."""
    snapshot = db.query(DashboardSnapshot).filter(DashboardSnapshot.id == snapshot_id).first()

    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    db.delete(snapshot)
    db.commit()

    return {"message": "Snapshot deleted successfully"}


@router.get("/query/data")
async def query_snapshot_data(
    promql_query: str,
    time_range: str = "1h",
    db: Session = Depends(get_db)
):
    """
    Query Prometheus data for snapshot panels.
    
    This is a public endpoint (no auth required) to allow snapshot pages
    to display live chart data.
    """
    import httpx
    from datetime import timedelta
    
    # Get the default datasource
    from app.models_dashboards import PrometheusDatasource
    datasource = db.query(PrometheusDatasource).filter(
        PrometheusDatasource.is_default == True
    ).first()
    
    if not datasource:
        datasource = db.query(PrometheusDatasource).first()
    
    if not datasource:
        return {"data": [], "error": "No datasource configured"}
    
    # Parse time range
    time_map = {
        '5m': timedelta(minutes=5),
        '15m': timedelta(minutes=15),
        '30m': timedelta(minutes=30),
        '1h': timedelta(hours=1),
        '3h': timedelta(hours=3),
        '6h': timedelta(hours=6),
        '12h': timedelta(hours=12),
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
    }
    duration = time_map.get(time_range, timedelta(hours=1))
    
    end = datetime.utcnow()
    start = end - duration
    
    # Calculate step (aim for ~100 data points)
    step_seconds = max(15, int(duration.total_seconds() / 100))
    if step_seconds < 60:
        step = f"{step_seconds}s"
    elif step_seconds < 3600:
        step = f"{step_seconds // 60}m"
    else:
        step = f"{step_seconds // 3600}h"
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{datasource.url}/api/v1/query_range",
                params={
                    "query": promql_query,
                    "start": start.timestamp(),
                    "end": end.timestamp(),
                    "step": step
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return {"data": data.get("data", {}).get("result", [])}
                else:
                    return {"data": [], "error": data.get("error", "Query failed")}
            else:
                return {"data": [], "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"data": [], "error": str(e)}
