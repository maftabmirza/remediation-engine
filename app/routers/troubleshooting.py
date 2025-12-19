"""
Troubleshooting API Router
Endpoints for alert correlation, investigation paths, and root cause analysis.
"""
import logging
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, User
from app.schemas_troubleshooting import (
    AlertCorrelationResponse,
    RootCauseAnalysis,
    InvestigationPath
)
from app.services.correlation_service import CorrelationService
from app.services.troubleshooting_service import TroubleshootingService
from app.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/alerts/{alert_id}/correlation", response_model=AlertCorrelationResponse)
async def get_alert_correlation(
    alert_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the correlation group for an alert.
    If none exists, it attempts to find or create one based on current context.
    """
    logger.info(f"Troubleshooting: Fetching alert {alert_id} for correlation")
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        logger.error(f"Troubleshooting: Alert {alert_id} not found in DB")
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found in troubleshooting endpoint")
    
    logger.info(f"Troubleshooting: Found alert {alert.alert_name}")
    
    service = CorrelationService(db)
    correlation = service.find_or_create_correlation(alert)
    
    return correlation


@router.post("/alerts/{alert_id}/analyze-root-cause", response_model=RootCauseAnalysis)
async def analyze_root_cause(
    alert_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger Root Cause Analysis for an alert's correlation group.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    service = CorrelationService(db)
    correlation = service.find_or_create_correlation(alert)
    
    # Analyze
    # Analyze (async LLM call)
    analysis_result = await service.analyze_root_cause(correlation.id)
    
    return RootCauseAnalysis(
        root_cause=analysis_result.get("root_cause", "Unknown"),
        confidence=analysis_result.get("confidence", 0.5),
        reasoning=analysis_result.get("reasoning", []),
        related_alerts=[a.id for a in correlation.alerts],
        recommended_actions=analysis_result.get("affected_services", []) # Using affected services as placeholder for now
    )


@router.get("/alerts/{alert_id}/investigation-path", response_model=InvestigationPath)
async def get_investigation_path(
    alert_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a step-by-step investigation path for this alert.
    """
    service = TroubleshootingService(db)
    msg = "Generating investigation path (async LLM)..."
    logger.info(msg)
    path = await service.generate_investigation_path(alert_id)
    
    if not path:
        raise HTTPException(status_code=404, detail="Could not generate investigation path")
    
    return path
