"""
Webhook endpoint for Alertmanager

Handles incoming alerts from Alertmanager and triggers:
1. Rule matching
2. Auto-analysis via LLM
3. Auto-remediation via runbooks
"""
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.database import get_db, get_async_db
from app.models import Alert, LLMProvider, IncidentMetrics
from app.schemas import AlertmanagerWebhook
from app.services.rules_engine import find_matching_rule
from app.services.llm_service import analyze_alert
from app.metrics import (
    ALERTS_RECEIVED, ALERTS_PROCESSED, ALERTS_ANALYZED,
    WEBHOOK_REQUESTS, WEBHOOK_DURATION
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Webhook"])

# Module-level PII service instance (will be injected)
_pii_service = None


def set_pii_service(pii_service):
    """Set the PII service instance for alert data scanning."""
    global _pii_service
    _pii_service = pii_service


async def perform_auto_remediation(alert_id: str):
    """
    Background task to check for matching runbook triggers
    and initiate auto-remediation if configured.
    """
    from app.database import AsyncSessionLocal
    from app.services.trigger_matcher import AlertTriggerMatcher
    
    async with AsyncSessionLocal() as db:
        try:
            from sqlalchemy import select
            from app.models import Alert as AlertModel
            
            result = await db.execute(
                select(AlertModel).where(AlertModel.id == alert_id)
            )
            alert = result.scalar_one_or_none()
            
            if not alert:
                logger.error(f"Alert {alert_id} not found for auto-remediation check")
                return
            
            logger.info(f"Checking auto-remediation triggers for alert: {alert.alert_name}")
            
            # Match alert against runbook triggers
            from app.services.runbook_executor import RunbookExecutor
            from app.config import get_settings
            
            settings = get_settings()
            executor = RunbookExecutor(db, fernet_key=settings.encryption_key)
            
            trigger_matcher = AlertTriggerMatcher(db)
            remediation_result = await trigger_matcher.process_alert_for_remediation(alert, executor_service=executor)
            
            if remediation_result.get("auto_executed"):
                logger.info(
                    f"Auto-remediation triggered for alert {alert.alert_name}: "
                    f"{len(remediation_result['auto_executed'])} runbook(s)"
                )
            
            if remediation_result.get("pending_approval"):
                logger.info(
                    f"Remediation pending approval for alert {alert.alert_name}: "
                    f"{len(remediation_result['pending_approval'])} runbook(s)"
                )
            
            if remediation_result.get("blocked"):
                logger.warning(
                    f"Remediation blocked for alert {alert.alert_name}: "
                    f"{[b['reason'] for b in remediation_result['blocked']]}"
                )
                
        except Exception as e:
            logger.error(f"Auto-remediation check failed for alert {alert_id}: {str(e)}")
        finally:
            await db.close()


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
    logger.info("DEBUG: Webhook handler received request - PATCH VERIFICATION")
    
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
            
            # Scan and redact PII/secrets from alert data if service is available
            alert_annotations = annotations
            if _pii_service:
                try:
                    # Combine alert text for scanning
                    alert_text = f"{alert_name}\n"
                    if annotations:
                        alert_text += f"Summary: {annotations.get('summary', '')}\n"
                        alert_text += f"Description: {annotations.get('description', '')}\n"
                    if labels:
                        alert_text += f"Labels: {str(labels)}\n"
                    
                    # Detect PII/secrets
                    detection_response = await _pii_service.detect(
                        text=alert_text,
                        source_type="alert_data",
                        source_id=fingerprint
                    )
                    
                    # Log detections if any found
                    if detection_response.detections:
                        logger.info(
                            f"Detected {detection_response.detection_count} PII/secret(s) "
                            f"in alert '{alert_name}'"
                        )
                        
                        for detection in detection_response.detections:
                            await _pii_service.log_detection(
                                detection=detection.model_dump(),
                                source_type="alert_data",
                                source_id=fingerprint
                            )
                        
                        # Redact annotations if needed
                        if annotations:
                            annotations_text = f"Summary: {annotations.get('summary', '')}\n"
                            annotations_text += f"Description: {annotations.get('description', '')}"
                            
                            redaction_response = await _pii_service.redact(
                                text=annotations_text,
                                redaction_type="mask"
                            )
                            
                            # Parse redacted annotations
                            redacted_lines = redaction_response.redacted_text.split('\n')
                            if len(redacted_lines) >= 2:
                                alert_annotations = {
                                    **annotations,
                                    'summary': redacted_lines[0].replace('Summary: ', ''),
                                    'description': redacted_lines[1].replace('Description: ', '')
                                }
                        
                except Exception as e:
                    logger.error(f"PII detection failed for alert {alert_name}: {e}")
                    # Continue even if PII detection fails
            
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
                annotations_json=alert_annotations,  # Use redacted annotations
                raw_alert_json=alert_data.model_dump(),
                matched_rule_id=matched_rule.id if matched_rule else None,
                action_taken=action if action != "manual" else "pending",
                analyzed=False
            )
            
            db.add(alert)
            db.commit()
            db.refresh(alert)
            
            # Create incident metrics
            metric = IncidentMetrics(
                alert_id=alert.id,
                incident_started=timestamp,
                incident_detected=timestamp,  # Same as started for now
                service_name=job or labels.get("service") or labels.get("app"),
                severity=severity
            )
            metric.calculate_durations()
            db.add(metric)
            db.commit()
            
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
            
            # Always check for auto-remediation triggers (runs in background)
            background_tasks.add_task(
                perform_auto_remediation,
                str(alert.id)
            )
                
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
