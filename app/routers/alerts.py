"""
Alerts API endpoints
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.models import Alert, User, LLMProvider, AuditLog
from app.models_remediation import RunbookExecution
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
    time_range: str = Query("24h", pattern="^(24h|7d|30d)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get alert statistics and dashboard metrics.
    """
    window_map = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
    now = datetime.now(timezone.utc)
    start_time = now - window_map.get(time_range, timedelta(hours=24))

    def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
        """Normalize datetimes (naive or aware) to UTC-aware values."""
        if dt is None:
            return None
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    alerts_query = db.query(Alert).filter(Alert.timestamp >= start_time)
    alerts = alerts_query.all()

    total = len(alerts)
    analyzed = len([a for a in alerts if a.analyzed])
    pending = total - analyzed
    critical = len([a for a in alerts if a.severity == "critical"])
    warning = len([a for a in alerts if a.severity == "warning"])
    firing = len([a for a in alerts if a.status == "firing"])
    resolved = len([a for a in alerts if a.status == "resolved"])
    auto_analyzed = len([a for a in alerts if a.action_taken == "auto_analyze"])
    manually_analyzed = len([a for a in alerts if a.action_taken == "manual" and a.analyzed])
    ignored = len([a for a in alerts if a.action_taken == "ignore"])

    # Rule counts are not time-bound
    from app.models import AutoAnalyzeRule
    total_rules = db.query(AutoAnalyzeRule).count()
    enabled_rules = db.query(AutoAnalyzeRule).filter(AutoAnalyzeRule.enabled == True).count()

    # MTTA: time from alert creation to analysis
    mtta_values = [
        (to_utc(alert.analyzed_at) - to_utc(alert.timestamp)).total_seconds() / 60
        for alert in alerts
        if alert.analyzed_at and alert.timestamp
    ]
    mtta_minutes = round(sum(mtta_values) / len(mtta_values), 2) if mtta_values else 0.0

    # MTTR: time from execution start to completion for completed runbooks
    execution_query = db.query(RunbookExecution).filter(RunbookExecution.queued_at >= start_time)
    executions = execution_query.all()
    duration_minutes = []
    for execution in executions:
        start_clock = execution.started_at or execution.queued_at
        if execution.completed_at and start_clock:
            duration_minutes.append((execution.completed_at - start_clock).total_seconds() / 60)
    mttr_minutes = round(sum(duration_minutes) / len(duration_minutes), 2) if duration_minutes else 0.0

    total_executions = len(executions)
    successful_executions = len([ex for ex in executions if ex.status == "success"])
    remediation_success_rate = round((successful_executions / total_executions) * 100, 2) if total_executions else 0.0

    severity_distribution = {}
    for alert in alerts:
        key = alert.severity or "info"
        severity_distribution[key] = severity_distribution.get(key, 0) + 1

    # Trend buckets (hourly for 24h, daily otherwise)
    bucket_size = timedelta(hours=1) if time_range == "24h" else timedelta(days=1)
    trend_buckets = {}
    for alert in alerts:
        alert_ts = to_utc(alert.timestamp)
        if bucket_size >= timedelta(days=1):
            bucket_time = alert_ts.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            bucket_time = alert_ts.replace(minute=0, second=0, microsecond=0)
        bucket_key = bucket_time.isoformat()
        trend_buckets[bucket_key] = trend_buckets.get(bucket_key, 0) + 1

    # Fill empty buckets to keep charts smooth
    normalized_trend = []
    cursor = start_time.replace(minute=0, second=0, microsecond=0)
    if bucket_size >= timedelta(days=1):
        cursor = cursor.replace(hour=0)
    while cursor <= now:
        bucket_key = cursor.isoformat()
        normalized_trend.append({"bucket": bucket_key, "count": trend_buckets.get(bucket_key, 0)})
        cursor += bucket_size

    # Top sources by instance
    source_counts = {}
    for alert in alerts:
        source = alert.instance or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1
    top_sources = [
        {"source": source, "count": count}
        for source, count in sorted(source_counts.items(), key=lambda item: item[1], reverse=True)[:5]
    ]

    active_incidents = [
        {
            "id": alert.id,
            "alert_name": alert.alert_name,
            "severity": alert.severity,
            "timestamp": to_utc(alert.timestamp),
            "status": alert.status,
        }
        for alert in alerts
        if alert.status != "resolved"
    ]
    active_incidents = sorted(active_incidents, key=lambda item: item["timestamp"], reverse=True)[:10]

    last_sync_time = max([to_utc(alert.timestamp) for alert in alerts], default=None)
    connection_status = "degraded" if total == 0 else "online"

    # Service Reliability Index: transparent, weighted view
    # Weights: 40% critical impact, 35% timeliness, 25% remediation success.
    critical_component = 0.0
    timeliness_component = 0.0
    remediation_component = (remediation_success_rate / 100) * 25  # percent to 0-25 range

    if total:
        critical_ratio = critical / total
        critical_component = max(0.0, 1 - critical_ratio) * 40

    # Timeliness scoring uses simple targets: 15m MTTA, 120m MTTR.
    target_mtta = 15
    target_mttr = 120
    mtta_score = max(0.0, min(1.0, 1 - (mtta_minutes / target_mtta if target_mtta else 0))) if mtta_minutes else 1.0
    mttr_score = max(0.0, min(1.0, 1 - (mttr_minutes / target_mttr if target_mttr else 0))) if mttr_minutes else 1.0
    timeliness_component = ((mtta_score + mttr_score) / 2) * 35

    reliability_index = round(min(100, max(0, critical_component + timeliness_component + remediation_component)))
    reliability_breakdown = {
        "critical_impact": round(critical_component, 2),
        "timeliness": round(timeliness_component, 2),
        "remediation": round(remediation_component, 2),
    }

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
        enabled_rules=enabled_rules,
        mtta_minutes=mtta_minutes,
        mttr_minutes=mttr_minutes,
        remediation_success_rate=remediation_success_rate,
        severity_distribution=severity_distribution,
        alert_trend=normalized_trend,
        top_sources=top_sources,
        active_incidents=active_incidents,
        reliability_index=reliability_index,
        reliability_breakdown=reliability_breakdown,
        last_sync_time=last_sync_time,
        connection_status=connection_status,
        time_range=time_range,
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
    alert.analyzed_at = datetime.now(timezone.utc)
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
