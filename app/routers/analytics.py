
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import MTTRAnalytics, MTTRBreakdown, TrendPoint, RegressionAlert
from app.services.auth_service import get_current_user
from app.services.metrics_analytics_service import MetricsAnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("/mttr/aggregate", response_model=MTTRAnalytics)
async def get_mttr_aggregate(
    metric_type: str = Query("time_to_resolve", pattern="^(time_to_detect|time_to_acknowledge|time_to_engage|time_to_resolve)$"),
    time_range: str = Query("30d", pattern="^(24h|7d|30d|90d)$"),
    service: Optional[str] = None,
    severity: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get aggregate MTTR statistics (avg, p50, p95, p99).
    """
    service_obj = MetricsAnalyticsService(db)
    return service_obj.get_aggregate_stats(
        metric_type=metric_type,
        time_range=time_range,
        service=service,
        severity=severity
    )

@router.get("/mttr/breakdown", response_model=MTTRBreakdown)
async def get_mttr_breakdown(
    dimension: str = Query("service_name", pattern="^(service_name|severity|resolution_type)$"),
    metric_type: str = Query("time_to_resolve", pattern="^(time_to_detect|time_to_acknowledge|time_to_engage|time_to_resolve)$"),
    time_range: str = Query("30d", pattern="^(24h|7d|30d|90d)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get MTTR breakdown by service, severity, or resolution type.
    """
    service_obj = MetricsAnalyticsService(db)
    return service_obj.get_breakdown(
        dimension=dimension,
        metric_type=metric_type,
        time_range=time_range
    )

@router.get("/mttr/trends", response_model=List[TrendPoint])
async def get_mttr_trends(
    metric_type: str = Query("time_to_resolve", pattern="^(time_to_detect|time_to_acknowledge|time_to_engage|time_to_resolve)$"),
    time_range: str = Query("30d", pattern="^(24h|7d|30d|90d)$"),
    interval: str = Query("day", pattern="^(day|week)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get MTTR trends over time.
    """
    service_obj = MetricsAnalyticsService(db)
    return service_obj.get_trends(
        metric_type=metric_type,
        time_range=time_range,
        interval=interval
    )

@router.get("/mttr/regressions", response_model=List[RegressionAlert])
async def get_mttr_regressions(
    metric_type: str = Query("time_to_resolve", pattern="^(time_to_detect|time_to_acknowledge|time_to_engage|time_to_resolve)$"),
    threshold: float = Query(20.0, ge=1.0, le=100.0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Detect performance regressions (degradation) compared to previous period.
    """
    service_obj = MetricsAnalyticsService(db)
    return service_obj.detect_regressions(
        metric_type=metric_type,
        threshold_percent=threshold
    )
