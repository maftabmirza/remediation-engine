"""
Panel Rows API

API endpoints for managing collapsible panel row groups in dashboards.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models_dashboards import PanelRow, Dashboard

router = APIRouter(
    prefix="/api/dashboards",
    tags=["panel_rows"]
)


# Pydantic schemas
class PanelRowCreate(BaseModel):
    title: str
    description: Optional[str] = None
    order: int = 0
    is_collapsed: bool = False


class PanelRowUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order: Optional[int] = None
    is_collapsed: Optional[bool] = None


class PanelRowResponse(BaseModel):
    id: str
    dashboard_id: str
    title: str
    description: Optional[str]
    order: int
    is_collapsed: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.post("/{dashboard_id}/rows", response_model=PanelRowResponse, status_code=status.HTTP_201_CREATED)
async def create_row(
    dashboard_id: str,
    row_data: PanelRowCreate,
    db: Session = Depends(get_db)
):
    """Create a new panel row in the dashboard."""
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    new_row = PanelRow(
        id=str(uuid.uuid4()),
        dashboard_id=dashboard_id,
        title=row_data.title,
        description=row_data.description,
        order=row_data.order,
        is_collapsed=row_data.is_collapsed
    )

    db.add(new_row)
    db.commit()
    db.refresh(new_row)

    return PanelRowResponse(
        id=new_row.id,
        dashboard_id=new_row.dashboard_id,
        title=new_row.title,
        description=new_row.description,
        order=new_row.order,
        is_collapsed=new_row.is_collapsed,
        created_at=new_row.created_at.isoformat() if new_row.created_at else "",
        updated_at=new_row.updated_at.isoformat() if new_row.updated_at else ""
    )


@router.get("/{dashboard_id}/rows", response_model=List[PanelRowResponse])
async def list_rows(
    dashboard_id: str,
    db: Session = Depends(get_db)
):
    """List all rows for a dashboard."""
    rows = db.query(PanelRow).filter(
        PanelRow.dashboard_id == dashboard_id
    ).order_by(PanelRow.order).all()

    return [
        PanelRowResponse(
            id=row.id,
            dashboard_id=row.dashboard_id,
            title=row.title,
            description=row.description,
            order=row.order,
            is_collapsed=row.is_collapsed,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else ""
        )
        for row in rows
    ]


@router.get("/{dashboard_id}/rows/{row_id}", response_model=PanelRowResponse)
async def get_row(
    dashboard_id: str,
    row_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific panel row."""
    row = db.query(PanelRow).filter(
        PanelRow.id == row_id,
        PanelRow.dashboard_id == dashboard_id
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Panel row not found")

    return PanelRowResponse(
        id=row.id,
        dashboard_id=row.dashboard_id,
        title=row.title,
        description=row.description,
        order=row.order,
        is_collapsed=row.is_collapsed,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else ""
    )


@router.put("/{dashboard_id}/rows/{row_id}", response_model=PanelRowResponse)
async def update_row(
    dashboard_id: str,
    row_id: str,
    row_update: PanelRowUpdate,
    db: Session = Depends(get_db)
):
    """Update a panel row."""
    row = db.query(PanelRow).filter(
        PanelRow.id == row_id,
        PanelRow.dashboard_id == dashboard_id
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Panel row not found")

    update_data = row_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(row, field, value)

    db.commit()
    db.refresh(row)

    return PanelRowResponse(
        id=row.id,
        dashboard_id=row.dashboard_id,
        title=row.title,
        description=row.description,
        order=row.order,
        is_collapsed=row.is_collapsed,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else ""
    )


@router.delete("/{dashboard_id}/rows/{row_id}")
async def delete_row(
    dashboard_id: str,
    row_id: str,
    db: Session = Depends(get_db)
):
    """Delete a panel row. Panels in this row will be unassigned (row_id set to NULL)."""
    from app.models_dashboards import DashboardPanel

    row = db.query(PanelRow).filter(
        PanelRow.id == row_id,
        PanelRow.dashboard_id == dashboard_id
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Panel row not found")

    # Unassign all panels from this row
    db.query(DashboardPanel).filter(
        DashboardPanel.row_id == row_id
    ).update({"row_id": None})

    db.delete(row)
    db.commit()

    return {"message": "Panel row deleted successfully"}
