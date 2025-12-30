"""
Query History API

API endpoints for tracking and managing PromQL query history.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid

from app.database import get_db
from app.models_dashboards import QueryHistory
from app.routers.auth import get_current_user
from app.models import User

router = APIRouter(
    prefix="/api/query-history",
    tags=["query_history"]
)


# Pydantic schemas
class QueryHistoryCreate(BaseModel):
    query: str
    datasource_id: Optional[str] = None
    dashboard_id: Optional[str] = None
    panel_id: Optional[str] = None
    time_range: Optional[str] = None
    execution_time_ms: Optional[int] = None
    series_count: Optional[int] = None
    status: str = "success"
    error_message: Optional[str] = None


class QueryHistoryResponse(BaseModel):
    id: str
    query: str
    datasource_id: Optional[str]
    dashboard_id: Optional[str]
    panel_id: Optional[str]
    time_range: Optional[str]
    execution_time_ms: Optional[int]
    series_count: Optional[int]
    status: str
    error_message: Optional[str]
    executed_by: Optional[str]
    is_favorite: bool
    executed_at: datetime

    class Config:
        from_attributes = True


@router.post("", response_model=QueryHistoryResponse, status_code=status.HTTP_201_CREATED)
async def create_query_history(
    history_data: QueryHistoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Record a query execution in history."""
    new_history = QueryHistory(
        id=str(uuid.uuid4()),
        query=history_data.query,
        datasource_id=history_data.datasource_id,
        dashboard_id=history_data.dashboard_id,
        panel_id=history_data.panel_id,
        time_range=history_data.time_range,
        execution_time_ms=history_data.execution_time_ms,
        series_count=history_data.series_count,
        status=history_data.status,
        error_message=history_data.error_message,
        executed_by=current_user.username
    )

    db.add(new_history)
    db.commit()
    db.refresh(new_history)

    return new_history


@router.get("", response_model=List[QueryHistoryResponse])
async def list_query_history(
    limit: int = Query(default=50, ge=1, le=500),
    dashboard_id: Optional[str] = None,
    favorites_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List query history with optional filtering."""
    query = db.query(QueryHistory).filter(
        QueryHistory.executed_by == current_user.username
    )

    if dashboard_id:
        query = query.filter(QueryHistory.dashboard_id == dashboard_id)

    if favorites_only:
        query = query.filter(QueryHistory.is_favorite == True)

    history = query.order_by(desc(QueryHistory.executed_at)).limit(limit).all()

    return history


@router.get("/{history_id}", response_model=QueryHistoryResponse)
async def get_query_history(
    history_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific query history entry."""
    history = db.query(QueryHistory).filter(
        QueryHistory.id == history_id,
        QueryHistory.executed_by == current_user.username
    ).first()

    if not history:
        raise HTTPException(status_code=404, detail="Query history not found")

    return history


@router.put("/{history_id}/favorite", response_model=QueryHistoryResponse)
async def toggle_favorite(
    history_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle favorite status for a query."""
    history = db.query(QueryHistory).filter(
        QueryHistory.id == history_id,
        QueryHistory.executed_by == current_user.username
    ).first()

    if not history:
        raise HTTPException(status_code=404, detail="Query history not found")

    history.is_favorite = not history.is_favorite
    db.commit()
    db.refresh(history)

    return history


@router.delete("/{history_id}")
async def delete_query_history(
    history_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a query history entry."""
    history = db.query(QueryHistory).filter(
        QueryHistory.id == history_id,
        QueryHistory.executed_by == current_user.username
    ).first()

    if not history:
        raise HTTPException(status_code=404, detail="Query history not found")

    db.delete(history)
    db.commit()

    return {"message": "Query history deleted successfully"}


@router.delete("")
async def clear_query_history(
    dashboard_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear query history (optionally filtered by dashboard)."""
    query = db.query(QueryHistory).filter(
        QueryHistory.executed_by == current_user.username
    )

    if dashboard_id:
        query = query.filter(QueryHistory.dashboard_id == dashboard_id)

    count = query.delete()
    db.commit()

    return {"message": f"Cleared {count} query history entries"}
