"""
Webhook endpoint for Alertmanager
"""
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models import Alert, LLMProvider
from app.schemas import AlertmanagerWebhook
from app.services.rules_engine import find_matching_rule
from app.services.llm_service import analyze_alert
from app.metrics import (
    ALERTS_RECEIVED, ALERTS_PROCESSED, ALERTS_ANALYZED,
    WEBHOOK_REQUESTS, WEBHOOK_DURATION
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhook"])


async def perform_auto_analysis(alert_id: str):
    """
    Background task to perform auto-analysis on an alert.
    """
    from app.database import SessionLocal
    
    db = SessionLocal()
    
    try:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            logger.error(f"Alert {alert_id} not found for auto-analysis")
            return
        
        logger.info(f"Starting auto-analysis for alert: {alert.alert_name}")
        
        analysis, recommendations, provider = await analyze_alert(db, alert)
        
        alert.analyzed = True
        alert.analyzed_at = datetime.now(timezone.utc)
        alert.llm_provider_id = provider.id
        alert.ai_analysis = analysis
        alert.recommendations_json = recommendations
        alert.analysis_count = 1
        
        db.commit()
        logger.info(f"Auto-analysis completed for alert: {alert.alert_name}")
        
        # Record successful analysis metric
        ALERTS_ANALYZED.labels(provider=provider.name, status="success").inc()
        
    except Exception as e:
        logger.error(f"Auto-analysis failed for alert {alert_id}: {str(e)}")
        ALERTS_ANALYZED.labels(provider="unknown", status="error").inc()
    finally:
        db.close()


@router.post("/alerts")
async def receive_alertmanager_webhook(
    webhook: AlertmanagerWebhook,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Receive alerts from Alertmanager.
    
    This endpoint:
    1. Stores all incoming alerts
    2. Matches each alert against rules
    3. Based on rule action:
       - auto_analyze: Queue for AI analysis
       - ignore: Store but mark as ignored
       - manual: Store and wait for user action
    """
    start_time = time.time()
    WEBHOOK_REQUESTS.inc()
    
    from app.config import get_settings
    settings = get_settings()
    
    processed = []
    
    for alert_data in webhook.alerts:
        try:
            # Extract alert details
            labels = alert_data.labels
            annotations = alert_data.annotations
            
            alert_name = labels.get("alertname", "Unknown")
            severity = labels.get("severity", "unknown")
            instance = labels.get("instance", "")
            job = labels.get("job", "")
            fingerprint = alert_data.fingerprint
            
            # Record alert received metric
            ALERTS_RECEIVED.labels(severity=severity, status=alert_data.status).inc()
            
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(alert_data.startsAt.replace("Z", "+00:00"))
            except:
                timestamp = datetime.now(timezone.utc)
            
            # Check if alert already exists (by fingerprint and timestamp)
            existing = db.query(Alert).filter(
                Alert.fingerprint == fingerprint,
                Alert.timestamp == timestamp
            ).first()
            
            if existing:
                # Update status if changed
                if existing.status != alert_data.status:
                    existing.status = alert_data.status
                    db.commit()
                processed.append({
                    "alert_name": alert_name,
                    "action": "updated",
                    "id": str(existing.id)
                })
                continue
            
            # Find matching rule
            matched_rule, action = find_matching_rule(db, alert_name, severity, instance, job)
            
            # Handle ignored alerts
            if action == "ignore":
                logger.info(f"Ignoring alert: {alert_name} (matched rule: {matched_rule.name if matched_rule else 'none'})")
                ALERTS_PROCESSED.labels(action="ignore").inc()
                processed.append({
                    "alert_name": alert_name,
                    "action": "ignored"
                })
                continue
            
            # Create alert record
            alert = Alert(
                fingerprint=fingerprint,
                timestamp=timestamp,
                alert_name=alert_name,
                severity=severity,
                instance=instance,
                job=job,
                status=alert_data.status,
                labels_json=labels,
                annotations_json=annotations,
                raw_alert_json=alert_data.model_dump(),
                matched_rule_id=matched_rule.id if matched_rule else None,
                action_taken=action if action != "manual" else "pending",
                analyzed=False
            )
            
            db.add(alert)
            db.commit()
            db.refresh(alert)
            
            logger.info(f"Stored alert: {alert_name} (action: {action})")
            
            # Queue auto-analysis if needed
            if action == "auto_analyze":
                background_tasks.add_task(
                    perform_auto_analysis,
                    str(alert.id)
                )
                ALERTS_PROCESSED.labels(action="auto_analyze").inc()
                processed.append({
                    "alert_name": alert_name,
                    "action": "auto_analyze_queued",
                    "id": str(alert.id)
                })
            else:
                ALERTS_PROCESSED.labels(action="manual").inc()
                processed.append({
                    "alert_name": alert_name,
                    "action": "stored_pending",
                    "id": str(alert.id)
                })
                
        except Exception as e:
            logger.error(f"Error processing alert: {str(e)}")
            ALERTS_PROCESSED.labels(action="error").inc()
            processed.append({
                "alert_name": alert_data.labels.get("alertname", "Unknown"),
                "action": "error",
                "error": str(e)
            })
    
    # Record webhook processing duration
    WEBHOOK_DURATION.observe(time.time() - start_time)
    
    return {
        "status": "received",
        "processed": len(processed),
        "alerts": processed
    }


@router.get("/health")
async def webhook_health():
    """
    Health check endpoint for webhook receiver.
    """
    return {"status": "healthy", "service": "alertmanager-webhook"}
