"""
ITSM Sync Background Worker

Periodically fetches changes from ITSM systems
and runs correlation analysis
"""
import logging
import json
from datetime import timedelta, datetime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models_itsm import ITSMIntegration, ChangeEvent
from app.services.itsm_connector import GenericAPIConnector
from app.services.change_impact_service import ChangeImpactService
from app.utils.crypto import decrypt_value

logger = logging.getLogger(__name__)


def utc_now():
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)


async def sync_itsm_changes():
    """
    Main sync job - runs every 15 minutes

    1. Load enabled integrations
    2. For each integration:
       - Fetch changes since last sync
       - Store as ChangeEvent records
       - Run correlation analysis
    3. Update sync status
    """
    db = SessionLocal()

    try:
        # Get all enabled integrations
        integrations = db.query(ITSMIntegration).filter(
            ITSMIntegration.is_enabled == True
        ).all()

        if not integrations:
            logger.info("No enabled ITSM integrations")
            return

        logger.info(f"Syncing {len(integrations)} ITSM integrations...")

        for integration in integrations:
            try:
                await _sync_integration(db, integration)
            except Exception as e:
                logger.error(f"Failed to sync integration {integration.name}: {e}", exc_info=True)
                # Mark as failed but continue with others
                integration.last_sync = utc_now()
                integration.last_sync_status = 'failed'
                integration.last_error = str(e)
                db.commit()
                continue

        logger.info("✅ ITSM sync complete")

    except Exception as e:
        logger.error(f"ITSM sync failed: {e}", exc_info=True)
    finally:
        db.close()


async def _sync_integration(db: Session, integration: ITSMIntegration):
    """Sync a single ITSM integration"""
    logger.info(f"Syncing {integration.name}...")

    # Decrypt config
    config_json = decrypt_value(integration.config_encrypted)
    config = json.loads(config_json)

    # Create connector
    connector = GenericAPIConnector(config)

    # Determine time range
    if integration.last_sync:
        # Fetch changes since last sync
        start_time = integration.last_sync
    else:
        # First sync - fetch last 24 hours
        start_time = utc_now() - timedelta(hours=24)

    end_time = utc_now()

    # Fetch changes
    logger.info(f"Fetching changes from {start_time} to {end_time}")

    try:
        records = connector.fetch_changes(since=start_time)
    except Exception as e:
        logger.error(f"Failed to fetch changes: {e}")
        raise

    logger.info(f"Fetched {len(records)} changes")

    # Store changes
    new_changes = []
    for record in records:
        # Check if already exists
        existing = db.query(ChangeEvent).filter(
            ChangeEvent.change_id == record.get('change_id')
        ).first()

        if not existing:
            change = ChangeEvent(
                change_id=record['change_id'],
                change_type=record.get('change_type', 'deployment'),
                service_name=record.get('service_name'),
                description=record.get('description'),
                timestamp=record.get('timestamp', utc_now()),
                source=str(integration.id),
                change_metadata=record  # Store full record
            )
            db.add(change)
            db.flush()
            new_changes.append(change)
        else:
            logger.debug(f"Change {record.get('change_id')} already exists")

    db.commit()

    logger.info(f"Stored {len(new_changes)} new changes")

    # Run correlation analysis on new changes
    if new_changes:
        impact_service = ChangeImpactService(db)

        for change in new_changes:
            try:
                analysis = impact_service.analyze_change_impact(change)
                logger.debug(
                    f"Change {change.change_id}: "
                    f"correlation={analysis.correlation_score:.2f}, "
                    f"impact={analysis.impact_level}"
                )
            except Exception as e:
                logger.error(f"Failed to analyze change {change.change_id}: {e}")
                continue

    # Update sync status
    integration.last_sync = end_time
    integration.last_sync_status = 'success'
    integration.last_error = None
    db.commit()

    logger.info(f"✅ {integration.name} synced successfully")


def start_itsm_sync_jobs(scheduler):
    """Register ITSM sync jobs with scheduler"""
    
    # Sync job - every 15 minutes
    scheduler.add_job(
        sync_itsm_changes,
        'interval',
        minutes=15,
        id='sync_itsm_changes',
        replace_existing=True,
        name='ITSM Change Sync'
    )

    logger.info("✅ ITSM sync jobs registered")
