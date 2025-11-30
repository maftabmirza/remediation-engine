"""
Alerts API endpoints
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.models import Alert, User, LLMProvider, AuditLog
from app.schemas import (
    AlertResponse, AlertListResponse, AnalyzeRequest, 
    AnalysisResponse, StatsResponse
)
from app.services.auth_service import get_current_user
from app.services.llm_service import analyze_alert

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    severity: Optional[str] = None,
    status: Optional[str] = None,
    analyzed: Optional[bool] = None,
    alert_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List alerts with pagination and filtering.
    """
    query = db.query(Alert)
    
    # Apply filters
    if severity:
        query = query.filter(Alert.severity == severity)
    if status:
        query = query.filter(Alert.status == status)
    if analyzed is not None:
        query = query.filter(Alert.analyzed == analyzed)
    if alert_name:
        query = query.filter(Alert.alert_name.ilike(f"%{alert_name}%"))
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size
    
    # Get paginated results
    alerts = query.order_by(desc(Alert.timestamp)).offset(offset).limit(page_size).all()
    
    return AlertListResponse(
        alerts=[AlertResponse.model_validate(a) for a in alerts],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get alert statistics.
    """
    total = db.query(Alert).count()
    analyzed = db.query(Alert).filter(Alert.analyzed == True).count()
    pending = db.query(Alert).filter(Alert.analyzed == False).count()
    critical = db.query(Alert).filter(Alert.severity == "critical").count()
    warning = db.query(Alert).filter(Alert.severity == "warning").count()
    firing = db.query(Alert).filter(Alert.status == "firing").count()
    resolved = db.query(Alert).filter(Alert.status == "resolved").count()
    auto_analyzed = db.query(Alert).filter(Alert.action_taken == "auto_analyze").count()
    manually_analyzed = db.query(Alert).filter(Alert.action_taken == "manual", Alert.analyzed == True).count()
    ignored = db.query(Alert).filter(Alert.action_taken == "ignore").count()
    
    from app.models import AutoAnalyzeRule
    total_rules = db.query(AutoAnalyzeRule).count()
    enabled_rules = db.query(AutoAnalyzeRule).filter(AutoAnalyzeRule.enabled == True).count()
    
    return StatsResponse(
        total_alerts=total,
        analyzed_alerts=analyzed,
        pending_alerts=pending,
        critical_alerts=critical,
        warning_alerts=warning,
        firing_alerts=firing,
        resolved_alerts=resolved,
        auto_analyzed=auto_analyzed,
        manually_analyzed=manually_analyzed,
        ignored=ignored,
        total_rules=total_rules,
        enabled_rules=enabled_rules
    )


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific alert by ID.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/analyze", response_model=AnalysisResponse)
async def analyze_alert_endpoint(
    alert_id: UUID,
    request: Request,
    analyze_request: AnalyzeRequest = AnalyzeRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze an alert using AI.
    
    - If alert is already analyzed, returns cached analysis (unless force=true)
    - Can specify a specific LLM provider or use default
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    # Check if already analyzed and not forcing re-analysis
    if alert.analyzed and not analyze_request.force:
        return AnalysisResponse(
            alert_id=alert.id,
            analysis=alert.ai_analysis,
            recommendations=alert.recommendations_json or [],
            llm_provider=alert.llm_provider.name if alert.llm_provider else "Unknown",
            analyzed_at=alert.analyzed_at,
            analysis_count=alert.analysis_count
        )
    
    # Get provider if specified
    provider = None
    if analyze_request.llm_provider_id:
        provider = db.query(LLMProvider).filter(
            LLMProvider.id == analyze_request.llm_provider_id,
            LLMProvider.is_enabled == True
        ).first()
        
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Specified LLM provider not found or not enabled"
            )
    
    # Perform analysis
    try:
        analysis, recommendations, used_provider = await analyze_alert(db, alert, provider)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    
    # Update alert
    alert.analyzed = True
    alert.analyzed_at = datetime.utcnow()
    alert.analyzed_by = current_user.id
    alert.llm_provider_id = used_provider.id
    alert.ai_analysis = analysis
    alert.recommendations_json = recommendations
    alert.analysis_count = (alert.analysis_count or 0) + 1
    
    if alert.action_taken == "pending" or not alert.action_taken:
        alert.action_taken = "manual"
    
    db.commit()
    db.refresh(alert)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="analyze_alert",
        resource_type="alert",
        resource_id=alert.id,
        details_json={
            "alert_name": alert.alert_name,
            "provider": used_provider.name,
            "force": analyze_request.force
        },
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    db.commit()
    
    return AnalysisResponse(
        alert_id=alert.id,
        analysis=alert.ai_analysis,
        recommendations=alert.recommendations_json or [],
        llm_provider=used_provider.name,
        analyzed_at=alert.analyzed_at,
        analysis_count=alert.analysis_count
    )


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete an alert.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="delete_alert",
        resource_type="alert",
        resource_id=alert.id,
        details_json={"alert_name": alert.alert_name},
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    
    db.delete(alert)
    db.commit()
    
    return {"message": "Alert deleted successfully"}
