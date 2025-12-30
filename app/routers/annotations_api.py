"""
Annotations API Router

API endpoints for creating, reading, updating, and deleting dashboard annotations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid

from app.database import get_db
from app.models_dashboards import DashboardAnnotation, Dashboard, PrometheusPanel

router = APIRouter(
    prefix="/api/annotations",
    tags=["annotations"]
)


# Pydantic models for request/response
class AnnotationCreate(BaseModel):
    dashboard_id: Optional[str] = None
    panel_id: Optional[str] = None
    time: datetime
    time_end: Optional[datetime] = None
    text: str
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    color: str = "#FF6B6B"
    icon: Optional[str] = None
    created_by: Optional[str] = None


class AnnotationUpdate(BaseModel):
    time: Optional[datetime] = None
    time_end: Optional[datetime] = None
    text: Optional[str] = None
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class AnnotationResponse(BaseModel):
    id: str
    dashboard_id: Optional[str]
    panel_id: Optional[str]
    time: datetime
    time_end: Optional[datetime]
    text: str
    title: Optional[str]
    tags: Optional[List[str]]
    color: str
    icon: Optional[str]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


@router.post("", response_model=AnnotationResponse)
async def create_annotation(
    annotation: AnnotationCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new annotation.

    Annotations can be attached to:
    - A specific dashboard (dashboard_id)
    - A specific panel within a dashboard (dashboard_id + panel_id)
    - Global (no dashboard_id or panel_id)
    """
    # Validate references
    if annotation.dashboard_id:
        dashboard = db.query(Dashboard).filter(Dashboard.id == annotation.dashboard_id).first()
        if not dashboard:
            raise HTTPException(status_code=404, detail="Dashboard not found")

    if annotation.panel_id:
        panel = db.query(PrometheusPanel).filter(PrometheusPanel.id == annotation.panel_id).first()
        if not panel:
            raise HTTPException(status_code=404, detail="Panel not found")

    # Create annotation
    db_annotation = DashboardAnnotation(
        id=str(uuid.uuid4()),
        dashboard_id=annotation.dashboard_id,
        panel_id=annotation.panel_id,
        time=annotation.time,
        time_end=annotation.time_end,
        text=annotation.text,
        title=annotation.title,
        tags=annotation.tags,
        color=annotation.color,
        icon=annotation.icon,
        created_by=annotation.created_by
    )

    db.add(db_annotation)
    db.commit()
    db.refresh(db_annotation)

    return db_annotation


@router.get("", response_model=List[AnnotationResponse])
async def get_annotations(
    dashboard_id: Optional[str] = Query(None, description="Filter by dashboard ID"),
    panel_id: Optional[str] = Query(None, description="Filter by panel ID"),
    from_time: Optional[datetime] = Query(None, description="Start time for filtering"),
    to_time: Optional[datetime] = Query(None, description="End time for filtering"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    db: Session = Depends(get_db)
):
    """
    Get annotations with optional filtering.

    Filters:
    - dashboard_id: Get annotations for a specific dashboard
    - panel_id: Get annotations for a specific panel
    - from_time/to_time: Time range filter
    - tags: Filter by tags (comma-separated)
    """
    query = db.query(DashboardAnnotation)

    # Apply filters
    if dashboard_id:
        query = query.filter(DashboardAnnotation.dashboard_id == dashboard_id)

    if panel_id:
        query = query.filter(DashboardAnnotation.panel_id == panel_id)

    if from_time:
        query = query.filter(
            or_(
                DashboardAnnotation.time >= from_time,
                and_(
                    DashboardAnnotation.time_end.isnot(None),
                    DashboardAnnotation.time_end >= from_time
                )
            )
        )

    if to_time:
        query = query.filter(DashboardAnnotation.time <= to_time)

    # Filter by tags
    if tags:
        tag_list = [tag.strip() for tag in tags.split(',')]
        # Cast JSON to text and use LIKE for matching since PostgreSQL JSON doesn't support direct contains
        from sqlalchemy import cast, String
        for tag in tag_list:
            query = query.filter(cast(DashboardAnnotation.tags, String).like(f'%"{tag}"%'))

    # Order by time descending
    annotations = query.order_by(DashboardAnnotation.time.desc()).all()

    return annotations


@router.get("/{annotation_id}", response_model=AnnotationResponse)
async def get_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific annotation by ID."""
    annotation = db.query(DashboardAnnotation).filter(DashboardAnnotation.id == annotation_id).first()

    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    return annotation


@router.put("/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(
    annotation_id: str,
    annotation_update: AnnotationUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing annotation."""
    annotation = db.query(DashboardAnnotation).filter(DashboardAnnotation.id == annotation_id).first()

    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    # Update fields if provided
    update_data = annotation_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(annotation, field, value)

    db.commit()
    db.refresh(annotation)

    return annotation


@router.delete("/{annotation_id}")
async def delete_annotation(
    annotation_id: str,
    db: Session = Depends(get_db)
):
    """Delete an annotation."""
    annotation = db.query(DashboardAnnotation).filter(DashboardAnnotation.id == annotation_id).first()

    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    db.delete(annotation)
    db.commit()

    return {"message": "Annotation deleted successfully", "id": annotation_id}


@router.get("/dashboard/{dashboard_id}/range", response_model=List[AnnotationResponse])
async def get_annotations_in_range(
    dashboard_id: str,
    from_time: datetime = Query(..., description="Start time"),
    to_time: datetime = Query(..., description="End time"),
    db: Session = Depends(get_db)
):
    """
    Get all annotations for a dashboard within a specific time range.

    This is optimized for chart rendering - returns all annotations that
    fall within or overlap with the specified time range.
    """
    annotations = db.query(DashboardAnnotation).filter(
        DashboardAnnotation.dashboard_id == dashboard_id,
        or_(
            and_(
                DashboardAnnotation.time >= from_time,
                DashboardAnnotation.time <= to_time
            ),
            and_(
                DashboardAnnotation.time_end.isnot(None),
                DashboardAnnotation.time <= to_time,
                DashboardAnnotation.time_end >= from_time
            )
        )
    ).order_by(DashboardAnnotation.time.asc()).all()

    return annotations
