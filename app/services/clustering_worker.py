"""
Alert Clustering Background Worker

Scheduled jobs for automated alert clustering:
- cluster_recent_alerts: Runs every 5 minutes
- cleanup_old_clusters: Runs daily at 2 AM
- AI summary generation: Async for large clusters
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import get_db
from app.models import Alert, AlertCluster, utc_now
from app.services.alert_clustering_service import AlertClusteringService

logger = logging.getLogger(__name__)


def cluster_recent_alerts(db: Session):
    """
    Cluster unclustered alerts from the last hour
    Runs every 5 minutes
    """
    try:
        logger.info("Starting alert clustering job")

        # Get unclustered alerts from last hour
        cutoff_time = utc_now() - timedelta(hours=1)
        unclustered_alerts = db.query(Alert).filter(
            Alert.cluster_id.is_(None),
            Alert.timestamp >= cutoff_time,
            Alert.status == 'firing'
        ).all()

        if not unclustered_alerts:
            logger.info("No unclustered alerts found")
            return

        logger.info(f"Found {len(unclustered_alerts)} unclustered alerts")

        # Run clustering
        service = AlertClusteringService(db)
        clusters = service.cluster_alerts(unclustered_alerts, strategy='auto')

        # Apply clustering
        created_clusters = service.apply_clustering(clusters)

        # Close inactive clusters
        closed_count = service.close_inactive_clusters(inactive_hours=24)

        logger.info(
            f"Clustering complete: {len(unclustered_alerts)} alerts → "
            f"{len(created_clusters)} clusters, {closed_count} clusters closed"
        )

        # Generate AI summaries asynchronously (non-blocking)
        if created_clusters:
            asyncio.create_task(_generate_summaries_async(created_clusters))

    except Exception as e:
        logger.error(f"Alert clustering job failed: {e}", exc_info=True)
        db.rollback()


async def _generate_summaries_async(clusters: List[AlertCluster]):
    """
    Generate AI summaries for clusters asynchronously
    Only for clusters with 3+ alerts
    """
    try:
        # Get a new database session for async operation
        db = next(get_db())

        from app.services.llm_service import generate_completion

        for cluster in clusters:
            # Only generate for clusters with 3+ alerts
            if cluster.alert_count < 3:
                continue

            # Skip if summary already exists
            if cluster.summary:
                continue

            try:
                # Get cluster alerts
                alerts = db.query(Alert).filter(
                    Alert.cluster_id == cluster.id
                ).limit(10).all()  # Limit to 10 for summary

                if not alerts:
                    continue

                # Build context for LLM
                alert_details = []
                for alert in alerts:
                    detail = f"- {alert.alert_name}"
                    if alert.instance:
                        detail += f" on {alert.instance}"
                    if alert.annotations_json:
                        summary = alert.annotations_json.get('summary', '')
                        if summary:
                            detail += f": {summary}"
                    alert_details.append(detail)

                context = f"""
Alert Cluster Summary Request:

Cluster Type: {cluster.cluster_type}
Alert Count: {cluster.alert_count}
Severity: {cluster.severity}
Time Range: {cluster.first_seen} to {cluster.last_seen}

Sample Alerts:
{chr(10).join(alert_details[:10])}

Please provide a concise 2-3 sentence summary of this alert cluster, 
focusing on the root cause and impact.
"""

                # Generate summary using llm_service function
                summary, _ = await generate_completion(db, context)

                # Update cluster
                cluster.summary = summary[:500]  # Limit length
                db.commit()

                logger.info(f"Generated summary for cluster {cluster.id}")

            except Exception as e:
                logger.error(f"Failed to generate summary for cluster {cluster.id}: {e}")
                continue

        db.close()

    except Exception as e:
        logger.error(f"AI summary generation failed: {e}", exc_info=True)


def cleanup_old_clusters(db: Session):
    """
    Delete inactive clusters older than 30 days
    Runs daily at 2 AM
    """
    try:
        logger.info("Starting cluster cleanup job")

        cutoff_time = utc_now() - timedelta(days=30)

        # Find old inactive clusters
        old_clusters = db.query(AlertCluster).filter(
            AlertCluster.is_active == False,
            AlertCluster.closed_at < cutoff_time
        ).all()

        if not old_clusters:
            logger.info("No old clusters to clean up")
            return

        # Unlink alerts from clusters before deletion
        for cluster in old_clusters:
            db.query(Alert).filter(
                Alert.cluster_id == cluster.id
            ).update({'cluster_id': None, 'clustered_at': None})

        # Delete clusters
        count = len(old_clusters)
        for cluster in old_clusters:
            db.delete(cluster)

        db.commit()

        logger.info(f"Cleaned up {count} old clusters")

    except Exception as e:
        logger.error(f"Cluster cleanup job failed: {e}", exc_info=True)
        db.rollback()


def start_clustering_jobs(scheduler: AsyncIOScheduler):
    """
    Register clustering jobs with the scheduler

    Args:
        scheduler: APScheduler instance from main.py
    """
    logger.info("Registering alert clustering jobs")

    # Job 1: Cluster recent alerts every 5 minutes
    scheduler.add_job(
        func='app.services.clustering_worker:cluster_recent_alerts_job',
        trigger='interval',
        minutes=5,
        id='cluster_recent_alerts',
        name='Cluster Recent Alerts',
        replace_existing=True,
        max_instances=1  # Prevent overlapping runs
    )

    # Job 2: Cleanup old clusters daily at 2 AM
    scheduler.add_job(
        func='app.services.clustering_worker:cleanup_old_clusters_job',
        trigger='cron',
        hour=2,
        minute=0,
        id='cleanup_old_clusters',
        name='Cleanup Old Clusters',
        replace_existing=True
    )

    logger.info("Alert clustering jobs registered successfully")


# Module-level wrapper functions for APScheduler
def cluster_recent_alerts_job():
    """Wrapper function for cluster_recent_alerts"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        cluster_recent_alerts(db)
    finally:
        db.close()


def cleanup_old_clusters_job():
    """Wrapper function for cleanup_old_clusters"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        cleanup_old_clusters(db)
    finally:
        db.close()
