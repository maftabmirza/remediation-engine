"""
Changes API Router

Endpoints for managing and viewing change events and their impact.
"""
import logging
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models_itsm import ChangeEvent, ChangeImpactAnalysis
from app.schemas_itsm import (
    ChangeEventCreate, ChangeEventResponse, ChangeEventDetail,
    ChangeImpactResponse, ChangeImpactSummary, ChangeTimelineResponse, ChangeTimelineEntry
)
from app.services.change_impact_service import ChangeImpactService
from app.routers.auth import get_current_user


def utc_now():
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/changes", tags=["changes"])


@router.get("", response_model=List[ChangeEventResponse])
async def list_changes(
    time_range: str = Query("7d", regex="^(24h|7d|30d|90d)$"),
    service_name: Optional[str] = None,
    change_type: Optional[str] = None,
    impact_level: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List change events with filters"""
    time_deltas = {
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
        '90d': timedelta(days=90)
    }
    
    cutoff = utc_now() - time_deltas[time_range]
    
    query = db.query(ChangeEvent).filter(
        ChangeEvent.timestamp >= cutoff
    )
    
    if service_name:
        query = query.filter(ChangeEvent.service_name == service_name)
    if change_type:
        query = query.filter(ChangeEvent.change_type == change_type)
    if impact_level:
        query = query.filter(ChangeEvent.impact_level == impact_level)
    
    # Pagination
    offset = (page - 1) * page_size
    changes = query.order_by(
        ChangeEvent.timestamp.desc()
    ).offset(offset).limit(page_size).all()
    
    return changes


@router.get("/timeline", response_model=ChangeTimelineResponse)
async def get_change_timeline(
    time_range: str = Query("7d", regex="^(24h|7d|30d)$"),
    service_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get change timeline with impact indicators"""
    time_deltas = {
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30)
    }
    
    start_date = utc_now() - time_deltas[time_range]
    end_date = utc_now()
    
    service = ChangeImpactService(db)
    timeline = service.get_change_timeline(start_date, end_date, service_name)
    
    # Count high impact
    high_impact_count = sum(1 for t in timeline if t.get('impact_level') == 'high')
    
    entries = [
        ChangeTimelineEntry(
            id=UUID(t['id']),
            change_id=t['change_id'],
            change_type=t['change_type'],
            service_name=t.get('service_name'),
            description=t.get('description'),
            timestamp=datetime.fromisoformat(t['timestamp']),
            start_time=datetime.fromisoformat(t['start_time']) if t.get('start_time') else None,
            end_time=datetime.fromisoformat(t['end_time']) if t.get('end_time') else None,
            associated_cis=t.get('associated_cis', []),
            application=t.get('application'),
            impact_level=t.get('impact_level'),
            incidents_after=t.get('incidents_after', 0)
        )
        for t in timeline
    ]
    
    return ChangeTimelineResponse(
        entries=entries,
        total_changes=len(entries),
        high_impact_count=high_impact_count
    )


@router.get("/high-impact")
async def get_high_impact_changes(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get high impact changes for the dashboard"""
    service = ChangeImpactService(db)
    changes = service.get_high_impact_changes(days=days, limit=limit)
    
    result = []
    for change in changes:
        impact = change.impact_analysis
        result.append(ChangeImpactSummary(
            change_id=change.change_id,
            change_description=change.description,
            timestamp=change.timestamp,
            correlation_score=change.correlation_score or 0.0,
            impact_level=change.impact_level or 'none',
            incidents_after=impact.incidents_after if impact else 0,
            critical_incidents=impact.critical_incidents if impact else 0,
            recommendation=impact.recommendation if impact else None
        ))
    
    return result


@router.get("/statistics")
async def get_change_statistics(
    days: int = Query(30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get aggregate change impact statistics"""
    service = ChangeImpactService(db)
    return service.get_impact_statistics(days=days)


@router.get("/{change_id}", response_model=ChangeEventDetail)
async def get_change(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific change event with impact analysis"""
    change = db.query(ChangeEvent).filter(
        ChangeEvent.change_id == change_id
    ).first()
    
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    
    # Build response with impact analysis
    impact = None
    if change.impact_analysis:
        impact = ChangeImpactResponse(
            id=change.impact_analysis.id,
            change_event_id=change.impact_analysis.change_event_id,
            incidents_after=change.impact_analysis.incidents_after,
            critical_incidents=change.impact_analysis.critical_incidents,
            correlation_score=change.impact_analysis.correlation_score,
            impact_level=change.impact_analysis.impact_level,
            recommendation=change.impact_analysis.recommendation,
            analyzed_at=change.impact_analysis.analyzed_at
        )
    
    return ChangeEventDetail(
        id=change.id,
        change_id=change.change_id,
        change_type=change.change_type,
        service_name=change.service_name,
        description=change.description,
        timestamp=change.timestamp,
        source=change.source,
        metadata=change.metadata or {},
        correlation_score=change.correlation_score,
        impact_level=change.impact_level,
        created_at=change.created_at,
        impact_analysis=impact
    )


@router.get("/{change_id}/incidents")
async def get_change_incidents(
    change_id: str,
    time_window_hours: int = Query(4, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get incidents correlated with a change event"""
    change = db.query(ChangeEvent).filter(
        ChangeEvent.change_id == change_id
    ).first()
    
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    
    service = ChangeImpactService(db)
    incidents = service.get_correlated_incidents(change.id, time_window_hours)
    
    return [
        {
            'id': str(i.id),
            'alert_name': i.alert_name,
            'severity': i.severity,
            'timestamp': i.timestamp.isoformat(),
            'instance': i.instance,
            'job': i.job,
            'status': i.status
        }
        for i in incidents
    ]


@router.post("/{change_id}/analyze")
async def analyze_change(
    change_id: str,
    time_window_hours: int = Query(4, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Manually trigger impact analysis for a change"""
    change = db.query(ChangeEvent).filter(
        ChangeEvent.change_id == change_id
    ).first()
    
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")
    
    service = ChangeImpactService(db)
    analysis = service.analyze_change_impact(change, time_window_hours)
    
    return {
        'change_id': change.change_id,
        'correlation_score': analysis.correlation_score,
        'impact_level': analysis.impact_level,
        'incidents_after': analysis.incidents_after,
        'critical_incidents': analysis.critical_incidents,
        'recommendation': analysis.recommendation
    }


@router.post("/webhook")
async def receive_change_webhook(
    data: ChangeEventCreate,
    db: Session = Depends(get_db)
):
    """Receive change event via webhook (no auth required for external systems)"""
    # Check if change already exists
    existing = db.query(ChangeEvent).filter(
        ChangeEvent.change_id == data.change_id
    ).first()
    
    if existing:
        # Update existing
        existing.change_type = data.change_type
        existing.service_name = data.service_name
        existing.description = data.description
        existing.timestamp = data.timestamp
        existing.start_time = data.start_time
        existing.end_time = data.end_time
        existing.associated_cis = data.associated_cis or []
        existing.application = data.application
        existing.change_metadata = data.metadata
        db.commit()
        
        return {"status": "updated", "id": str(existing.id)}
    
    # Create new
    change = ChangeEvent(
        change_id=data.change_id,
        change_type=data.change_type,
        service_name=data.service_name,
        description=data.description,
        timestamp=data.timestamp,
        start_time=data.start_time,
        end_time=data.end_time,
        associated_cis=data.associated_cis or [],
        application=data.application,
        source=data.source,
        change_metadata=data.metadata
    )
    db.add(change)
    db.commit()
    db.refresh(change)
    
    # Analyze impact
    service = ChangeImpactService(db)
    try:
        service.analyze_change_impact(change)
    except Exception as e:
        logger.error(f"Error analyzing change: {e}")
    
    logger.info(f"Received change webhook: {data.change_id}")
    return {"status": "created", "id": str(change.id)}
