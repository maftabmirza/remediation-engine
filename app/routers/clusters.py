"""
Alert Clusters API Router

REST endpoints for alert cluster management
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.database import get_db
from app.models import Alert, AlertCluster, User, utc_now
from app.schemas import (
    AlertClusterResponse,
    AlertClusterDetail,
    AlertClusterStats,
    AlertResponse
)
from app.services.auth_service import get_current_user
from app.services.alert_clustering_service import AlertClusteringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.get("", response_model=List[AlertClusterResponse])
async def list_clusters(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List alert clusters with filters and pagination
    """
    query = db.query(AlertCluster)

    # Apply filters
    if is_active is not None:
        query = query.filter(AlertCluster.is_active == is_active)

    if severity:
        query = query.filter(AlertCluster.severity == severity)

    # Order by last_seen descending (most recent first)
    query = query.order_by(AlertCluster.last_seen.desc())

    # Pagination
    total = query.count()
    offset = (page - 1) * page_size
    clusters = query.offset(offset).limit(page_size).all()

    # Add computed properties
    result = []
    for cluster in clusters:
        cluster_dict = {
            "id": cluster.id,
            "cluster_key": cluster.cluster_key,
            "severity": cluster.severity,
            "cluster_type": cluster.cluster_type,
            "alert_count": cluster.alert_count,
            "first_seen": cluster.first_seen,
            "last_seen": cluster.last_seen,
            "summary": cluster.summary,
            "is_active": cluster.is_active,
            "closed_at": cluster.closed_at,
            "closed_reason": cluster.closed_reason,
            "cluster_metadata": cluster.cluster_metadata,
            "created_at": cluster.created_at,
            "updated_at": cluster.updated_at,
            "duration_hours": cluster.duration_hours,
            "alerts_per_hour": cluster.alerts_per_hour
        }
        result.append(AlertClusterResponse(**cluster_dict))

    return result


@router.get("/{cluster_id}", response_model=AlertClusterDetail)
async def get_cluster(
    cluster_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get cluster details with member alerts
    """
    cluster = db.query(AlertCluster).filter(AlertCluster.id == cluster_id).first()

    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # Get member alerts
    alerts = db.query(Alert).filter(Alert.cluster_id == cluster_id).all()

    cluster_dict = {
        "id": cluster.id,
        "cluster_key": cluster.cluster_key,
        "severity": cluster.severity,
        "cluster_type": cluster.cluster_type,
        "alert_count": cluster.alert_count,
        "first_seen": cluster.first_seen,
        "last_seen": cluster.last_seen,
        "summary": cluster.summary,
        "is_active": cluster.is_active,
        "closed_at": cluster.closed_at,
        "closed_reason": cluster.closed_reason,
        "cluster_metadata": cluster.cluster_metadata,
        "created_at": cluster.created_at,
        "updated_at": cluster.updated_at,
        "duration_hours": cluster.duration_hours,
        "alerts_per_hour": cluster.alerts_per_hour,
        "alerts": alerts
    }

    return AlertClusterDetail(**cluster_dict)


@router.get("/{cluster_id}/alerts", response_model=List[AlertResponse])
async def get_cluster_alerts(
    cluster_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of alerts in cluster
    """
    # Verify cluster exists
    cluster = db.query(AlertCluster).filter(AlertCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # Get alerts
    query = db.query(Alert).filter(Alert.cluster_id == cluster_id)
    query = query.order_by(Alert.timestamp.desc())

    offset = (page - 1) * page_size
    alerts = query.offset(offset).limit(page_size).all()

    return alerts


@router.post("/{cluster_id}/close")
async def close_cluster(
    cluster_id: UUID,
    reason: str = Query("manual", description="Reason for closing"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually close/resolve a cluster
    """
    cluster = db.query(AlertCluster).filter(AlertCluster.id == cluster_id).first()

    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    if not cluster.is_active:
        raise HTTPException(status_code=400, detail="Cluster already closed")

    cluster.is_active = False
    cluster.closed_at = utc_now()
    cluster.closed_reason = reason

    db.commit()

    logger.info(f"Cluster {cluster_id} closed by user {current_user.username}")

    return {
        "status": "success",
        "message": "Cluster closed successfully",
        "cluster_id": str(cluster_id)
    }


@router.post("/{cluster_id}/merge/{target_cluster_id}")
async def merge_clusters(
    cluster_id: UUID,
    target_cluster_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Merge source cluster into target cluster
    """
    source = db.query(AlertCluster).filter(AlertCluster.id == cluster_id).first()
    target = db.query(AlertCluster).filter(AlertCluster.id == target_cluster_id).first()

    if not source or not target:
        raise HTTPException(status_code=404, detail="Cluster not found")

    if cluster_id == target_cluster_id:
        raise HTTPException(status_code=400, detail="Cannot merge cluster with itself")

    # Move all alerts from source to target
    db.query(Alert).filter(Alert.cluster_id == cluster_id).update({
        'cluster_id': target_cluster_id
    })

    # Update target cluster stats
    service = AlertClusteringService(db)
    target.update_stats(db)

    # Close source cluster
    source.is_active = False
    source.closed_at = utc_now()
    source.closed_reason = 'merged'

    db.commit()

    logger.info(f"Cluster {cluster_id} merged into {target_cluster_id} by user {current_user.username}")

    return {
        "status": "success",
        "message": "Clusters merged successfully",
        "source_cluster_id": str(cluster_id),
        "target_cluster_id": str(target_cluster_id)
    }


@router.post("/{cluster_id}/regenerate-summary")
async def regenerate_summary(
    cluster_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Regenerate AI summary for cluster
    """
    cluster = db.query(AlertCluster).filter(AlertCluster.id == cluster_id).first()

    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # Get cluster alerts
    alerts = db.query(Alert).filter(Alert.cluster_id == cluster_id).limit(10).all()

    if not alerts:
        raise HTTPException(status_code=400, detail="No alerts in cluster")

    try:
        from app.services.llm_service import LLMService

        llm_service = LLMService()

        # Build context
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
{chr(10).join(alert_details)}

Please provide a concise 2-3 sentence summary of this alert cluster, 
focusing on the root cause and impact.
"""

        # Generate summary
        summary = await llm_service.generate_analysis(context)

        # Update cluster
        cluster.summary = summary[:500]  # Limit length
        db.commit()

        logger.info(f"Summary regenerated for cluster {cluster_id} by user {current_user.username}")

        return {
            "status": "success",
            "message": "Summary regenerated successfully",
            "cluster_id": str(cluster_id),
            "summary": cluster.summary
        }

    except Exception as e:
        logger.error(f"Failed to regenerate summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")


@router.get("/stats/overview", response_model=AlertClusterStats)
async def get_cluster_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get dashboard statistics for clustering
    """
    # Total alerts
    total_alerts = db.query(Alert).filter(Alert.status == 'firing').count()

    # Clustered alerts
    clustered_alerts = db.query(Alert).filter(
        Alert.cluster_id.isnot(None),
        Alert.status == 'firing'
    ).count()

    # Active clusters
    active_clusters = db.query(AlertCluster).filter(
        AlertCluster.is_active == True
    ).count()

    # Noise reduction percentage
    if total_alerts > 0:
        noise_reduction_pct = ((total_alerts - active_clusters) / total_alerts) * 100
    else:
        noise_reduction_pct = 0.0

    # Average cluster size
    if active_clusters > 0:
        avg_cluster_size = clustered_alerts / active_clusters
    else:
        avg_cluster_size = 0.0

    # Largest cluster
    largest = db.query(func.max(AlertCluster.alert_count)).filter(
        AlertCluster.is_active == True
    ).scalar()
    largest_cluster_size = largest or 0

    return AlertClusterStats(
        total_alerts=total_alerts,
        clustered_alerts=clustered_alerts,
        active_clusters=active_clusters,
        noise_reduction_pct=round(noise_reduction_pct, 2),
        avg_cluster_size=round(avg_cluster_size, 2),
        largest_cluster_size=largest_cluster_size
    )
