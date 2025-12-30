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
    is_section_header: bool = False


class PanelRowUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order: Optional[int] = None
    is_collapsed: Optional[bool] = None
    is_section_header: Optional[bool] = None


class PanelRowResponse(BaseModel):
    id: str
    dashboard_id: str
    title: str
    description: Optional[str]
    order: int
    is_collapsed: bool
    is_section_header: bool
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

    # Handle section header flag by storing it in description
    description = row_data.description
    if row_data.is_section_header:
        if description:
            description = f"[SECTION_HEADER] {description}"
        else:
            description = "[SECTION_HEADER]"

    new_row = PanelRow(
        id=str(uuid.uuid4()),
        dashboard_id=dashboard_id,
        title=row_data.title,
        description=description,
        order=row_data.order,
        is_collapsed=row_data.is_collapsed
    )

    db.add(new_row)
    db.commit()
    db.refresh(new_row)

    # Compute is_section_header for response
    is_section_header = False
    clean_description = new_row.description
    if new_row.description and new_row.description.startswith("[SECTION_HEADER]"):
        is_section_header = True
        clean_description = new_row.description.replace("[SECTION_HEADER]", "").strip() or None

    return PanelRowResponse(
        id=new_row.id,
        dashboard_id=new_row.dashboard_id,
        title=new_row.title,
        description=clean_description,
        order=new_row.order,
        is_collapsed=new_row.is_collapsed,
        is_section_header=is_section_header,
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

    response_rows = []
    for row in rows:
        is_section_header = False
        clean_description = row.description
        if row.description and row.description.startswith("[SECTION_HEADER]"):
            is_section_header = True
            clean_description = row.description.replace("[SECTION_HEADER]", "").strip() or None
        
        response_rows.append(PanelRowResponse(
            id=row.id,
            dashboard_id=row.dashboard_id,
            title=row.title,
            description=clean_description,
            order=row.order,
            is_collapsed=row.is_collapsed,
            is_section_header=is_section_header,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else ""
        ))

    return response_rows


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
    
    is_section_header = False
    clean_description = row.description
    if row.description and row.description.startswith("[SECTION_HEADER]"):
        is_section_header = True
        clean_description = row.description.replace("[SECTION_HEADER]", "").strip() or None

    return PanelRowResponse(
        id=row.id,
        dashboard_id=row.dashboard_id,
        title=row.title,
        description=clean_description,
        order=row.order,
        is_collapsed=row.is_collapsed,
        is_section_header=is_section_header,
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
    
    # Handle is_section_header logic
    print(f"DEBUG: update_data before processing: {update_data}")
    if 'is_section_header' in update_data:
        is_header = update_data.pop('is_section_header')
        
        # Get current or new description
        current_desc = update_data.get('description', row.description)
        
        # Clean current description of any marker if it exists
        clean_desc = None
        if current_desc:
            clean_desc = current_desc.replace("[SECTION_HEADER]", "").strip() or None

        if is_header:
            if clean_desc:
                update_data['description'] = f"[SECTION_HEADER] {clean_desc}"
            else:
                update_data['description'] = "[SECTION_HEADER]"
        else:
            update_data['description'] = clean_desc
    elif 'description' in update_data:
        # If updating description but not changing header status, ensure we preserve header status if it was set
        if row.description and row.description.startswith("[SECTION_HEADER]"):
            desc = update_data['description']
            if desc:
                update_data['description'] = f"[SECTION_HEADER] {desc}"
            else:
                update_data['description'] = "[SECTION_HEADER]"
    
    print(f"DEBUG: update_data after processing: {update_data}")

    for field, value in update_data.items():
        setattr(row, field, value)

    db.commit()
    db.refresh(row)
    
    is_section_header = False
    clean_description = row.description
    if row.description and row.description.startswith("[SECTION_HEADER]"):
        is_section_header = True
        clean_description = row.description.replace("[SECTION_HEADER]", "").strip() or None

    return PanelRowResponse(
        id=row.id,
        dashboard_id=row.dashboard_id,
        title=row.title,
        description=clean_description,
        order=row.order,
        is_collapsed=row.is_collapsed,
        is_section_header=is_section_header,
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

    print(f"DEBUG: Deleting row {row_id} in dashboard {dashboard_id}. Found: {row}")

    if not row:
        raise HTTPException(status_code=404, detail="Panel row not found")

    # Unassign all panels from this row
    db.query(DashboardPanel).filter(
        DashboardPanel.row_id == row_id
    ).update({"row_id": None})

    db.delete(row)
    db.commit()

    return {"message": "Panel row deleted successfully"}
