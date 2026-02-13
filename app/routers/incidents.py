"""
Incidents API Router

Endpoints for managing ITSM incidents.
"""
import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models import User, LLMProvider, AuditLog
from app.models_itsm import IncidentEvent
from app.schemas_itsm import IncidentEventResponse, IncidentStatistics, IncidentAnalysisRequest
from app.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("", response_model=List[IncidentEventResponse])
async def list_incidents(
    time_range: str = Query("7d", pattern="^(24h|7d|30d|90d)$"),
    status: Optional[str] = None,
    severity: Optional[str] = None,
    priority: Optional[str] = None,
    service_name: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List incidents with filtering"""
    
    # Calculate start time
    now = datetime.now(timezone.utc)
    if time_range == "24h":
        start_time = now - timedelta(hours=24)
    elif time_range == "30d":
        start_time = now - timedelta(days=30)
    elif time_range == "90d":
        start_time = now - timedelta(days=90)
    else:  # 7d default
        start_time = now - timedelta(days=7)
        
    query = db.query(IncidentEvent).filter(IncidentEvent.created_at >= start_time)
    
    # Apply filters
    if status:
        if status.lower() == 'open':
            query = query.filter(IncidentEvent.is_open == True)
        elif status.lower() == 'closed':
            query = query.filter(IncidentEvent.is_open == False)
        else:
            query = query.filter(IncidentEvent.status.ilike(f"%{status}%"))
            
    if severity:
        query = query.filter(IncidentEvent.severity.ilike(f"%{severity}%"))
        
    if priority:
        query = query.filter(IncidentEvent.priority.ilike(f"%{priority}%"))
        
    if service_name:
        query = query.filter(IncidentEvent.service_name.ilike(f"%{service_name}%"))
        
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (IncidentEvent.title.ilike(search_term)) | 
            (IncidentEvent.description.ilike(search_term)) |
            (IncidentEvent.incident_id.ilike(search_term))
        )
        
    # Pagination
    total = query.count()
    incidents = query.order_by(desc(IncidentEvent.created_at))\
        .offset((page - 1) * page_size)\
        .limit(page_size)\
        .all()
        
    return incidents


@router.get("/statistics", response_model=IncidentStatistics)
async def get_incident_stats(
    time_range: str = Query("30d", pattern="^(24h|7d|30d|90d)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get incident statistics"""
    
    # Calculate start time
    now = datetime.now(timezone.utc)
    if time_range == "24h":
        start_time = now - timedelta(hours=24)
    elif time_range == "7d":
        start_time = now - timedelta(days=7)
    elif time_range == "90d":
        start_time = now - timedelta(days=90)
    else:  # 30d default
        start_time = now - timedelta(days=30)
        
    # Base query
    base_query = db.query(IncidentEvent).filter(IncidentEvent.created_at >= start_time)
    
    total_incidents = base_query.count()
    open_incidents = base_query.filter(IncidentEvent.is_open == True).count()
    resolved_incidents = base_query.filter(IncidentEvent.is_open == False).count()
    
    # Severity breakdown
    severity_counts = db.query(
        IncidentEvent.severity, func.count(IncidentEvent.id)
    ).filter(
        IncidentEvent.created_at >= start_time,
        IncidentEvent.severity.isnot(None)
    ).group_by(IncidentEvent.severity).all()
    
    severity_breakdown = {s: c for s, c in severity_counts}
    
    # Status breakdown
    status_counts = db.query(
        IncidentEvent.status, func.count(IncidentEvent.id)
    ).filter(
        IncidentEvent.created_at >= start_time,
        IncidentEvent.status.isnot(None)
    ).group_by(IncidentEvent.status).all()
    
    status_breakdown = {s: c for s, c in status_counts}
    
    # Avg resolution time (for resolved incidents in period)
    resolved_in_period = base_query.filter(
        IncidentEvent.resolved_at.isnot(None),
        IncidentEvent.resolved_at >= IncidentEvent.created_at
    ).with_entities(
        IncidentEvent.created_at, IncidentEvent.resolved_at
    ).all()
    
    avg_hours = 0.0
    if resolved_in_period:
        total_seconds = sum(
            (r.resolved_at - r.created_at).total_seconds() 
            for r in resolved_in_period
        )
        avg_hours = (total_seconds / len(resolved_in_period)) / 3600
    
    return IncidentStatistics(
        total_incidents=total_incidents,
        open_incidents=open_incidents,
        resolved_incidents=resolved_incidents,
        avg_resolution_time_hours=round(avg_hours, 2),
        severity_breakdown=severity_breakdown,
        status_breakdown=status_breakdown
    )


@router.get("/{incident_id}", response_model=IncidentEventResponse)
async def get_incident(
    incident_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific incident details"""
    incident = db.query(IncidentEvent).filter(IncidentEvent.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Enrich with provider name if analyzed
    response = IncidentEventResponse.model_validate(incident)
    if incident.llm_provider:
        response.llm_provider_name = incident.llm_provider.name
        
    return response


@router.post("/{incident_id}/analyze", response_model=IncidentEventResponse)
async def analyze_incident_endpoint(
    incident_id: UUID,
    request: Request,
    analyze_request: IncidentAnalysisRequest = IncidentAnalysisRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze an incident using AI.
    """
    incident = db.query(IncidentEvent).filter(IncidentEvent.id == incident_id).first()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    # Check if already analyzed and not forcing re-analysis
    if incident.analyzed and not analyze_request.force:
        response = IncidentEventResponse.model_validate(incident)
        if incident.llm_provider:
            response.llm_provider_name = incident.llm_provider.name
        return response
    
    # Get provider if specified
    provider = None
    if analyze_request.llm_provider_id:
        provider = db.query(LLMProvider).filter(
            LLMProvider.id == analyze_request.llm_provider_id,
            LLMProvider.is_enabled == True
        ).first()
        
        if not provider:
            raise HTTPException(
                status_code=400,
                detail="Specified LLM provider not found or not enabled"
            )
    
    # Perform analysis
    from app.services.llm_service import analyze_incident
    try:
        analysis, recommendations, used_provider = await analyze_incident(db, incident, provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    
    # Update incident
    incident.analyzed = True
    incident.analyzed_at = datetime.now(timezone.utc)
    incident.analyzed_by = current_user.id
    incident.llm_provider_id = used_provider.id
    incident.ai_analysis = analysis
    incident.recommendations_json = recommendations
    incident.analysis_count = (incident.analysis_count or 0) + 1
    
    db.commit()
    db.refresh(incident)
    
    # Audit log (using models directly to avoid circular imports if possible, or import at top)
    # For now skipping audit log to assume existing patterns or I'll add it if models are available
    # standardized logging for AI actions:
    from app.models import AuditLog, LLMProvider
    audit = AuditLog(
        user_id=current_user.id,
        action="analyze_incident",
        resource_type="incident",
        resource_id=incident.id,
        details_json={
            "incident_title": incident.title,
            "provider": used_provider.name,
            "force": analyze_request.force
        },
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    db.commit()
    
    response = IncidentEventResponse.model_validate(incident)
    response.llm_provider_name = used_provider.name
    return response
