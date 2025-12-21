"""
Prometheus Integration API

Provides endpoints to query Prometheus metrics and expose them
in the AIOps platform UI, eliminating the need to use Grafana separately.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta
import logging

from app.services.prometheus_service import (
    PrometheusClient,
    PrometheusConnectionError,
    PrometheusQueryError
)
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prometheus", tags=["Prometheus"])


@router.get("/health")
async def check_prometheus_health():
    """
    Check if Prometheus is reachable and responding

    Returns:
        Status and version information
    """
    settings = get_settings()

    if not settings.enable_prometheus_queries:
        return {
            "enabled": False,
            "message": "Prometheus queries are disabled in configuration"
        }

    try:
        async with PrometheusClient() as client:
            # Try to query Prometheus version
            result = await client.query("prometheus_build_info")

            return {
                "enabled": True,
                "status": "healthy",
                "url": settings.prometheus_url,
                "reachable": True
            }
    except PrometheusConnectionError as e:
        return {
            "enabled": True,
            "status": "unreachable",
            "url": settings.prometheus_url,
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"Prometheus health check failed: {e}")
        return {
            "enabled": True,
            "status": "error",
            "error": str(e)
        }


@router.get("/infrastructure")
async def get_infrastructure_metrics():
    """
    Get infrastructure health metrics for all monitored instances

    Returns CPU, memory, disk usage for each instance
    """
    settings = get_settings()

    if not settings.enable_prometheus_queries:
        raise HTTPException(
            status_code=503,
            detail="Prometheus queries are disabled"
        )

    try:
        async with PrometheusClient() as client:
            instances = await client.get_all_instances_health()

            return {
                "instances": instances,
                "total_count": len(instances),
                "healthy_count": sum(1 for i in instances if i.get("status") == "up")
            }
    except PrometheusConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach Prometheus: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to get infrastructure metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch infrastructure metrics"
        )


@router.get("/infrastructure/{instance}")
async def get_instance_metrics(instance: str):
    """
    Get detailed metrics for a specific instance

    Args:
        instance: Instance identifier (e.g., "server-01:9100")

    Returns:
        CPU, memory, disk metrics
    """
    settings = get_settings()

    if not settings.enable_prometheus_queries:
        raise HTTPException(
            status_code=503,
            detail="Prometheus queries are disabled"
        )

    try:
        async with PrometheusClient() as client:
            metrics = await client.get_infrastructure_metrics(instance)

            if all(v is None for v in metrics.values()):
                raise HTTPException(
                    status_code=404,
                    detail=f"No metrics found for instance {instance}"
                )

            return {
                "instance": instance,
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metrics for {instance}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch instance metrics"
        )


@router.get("/alert-trends")
async def get_alert_trends(hours: int = Query(default=24, ge=1, le=168)):
    """
    Get alert volume trends from Prometheus

    Args:
        hours: Number of hours to look back (1-168)

    Returns:
        Time series of alert counts
    """
    settings = get_settings()

    if not settings.enable_prometheus_queries:
        raise HTTPException(
            status_code=503,
            detail="Prometheus queries are disabled"
        )

    try:
        async with PrometheusClient() as client:
            trends = await client.get_alert_trends(hours)

            return {
                "time_range_hours": hours,
                "data_points": len(trends),
                "trends": trends
            }
    except Exception as e:
        logger.error(f"Failed to get alert trends: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch alert trends"
        )


@router.get("/alert-rate")
async def get_alert_rate():
    """
    Get current alert rate grouped by severity

    Returns:
        Current alerts per minute by severity
    """
    settings = get_settings()

    if not settings.enable_prometheus_queries:
        raise HTTPException(
            status_code=503,
            detail="Prometheus queries are disabled"
        )

    try:
        async with PrometheusClient() as client:
            rates = await client.get_alert_rate_by_severity()

            total_rate = sum(rates.values())

            return {
                "by_severity": rates,
                "total_rate": round(total_rate, 2),
                "unit": "alerts_per_minute"
            }
    except Exception as e:
        logger.error(f"Failed to get alert rate: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch alert rate"
        )


@router.get("/platform-metrics")
async def get_platform_metrics():
    """
    Get AIOps platform performance metrics

    Returns:
        Platform health, LLM usage, webhook stats, etc.
    """
    settings = get_settings()

    if not settings.enable_prometheus_queries:
        raise HTTPException(
            status_code=503,
            detail="Prometheus queries are disabled"
        )

    try:
        async with PrometheusClient() as client:
            metrics = await client.get_platform_metrics()

            return {
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Failed to get platform metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch platform metrics"
        )


@router.get("/clustering-metrics")
async def get_clustering_metrics():
    """
    Get alert clustering performance metrics from Prometheus

    Returns:
        Clustering stats (active clusters, noise reduction, etc.)
    """
    settings = get_settings()

    if not settings.enable_prometheus_queries:
        raise HTTPException(
            status_code=503,
            detail="Prometheus queries are disabled"
        )

    try:
        async with PrometheusClient() as client:
            metrics = await client.get_clustering_metrics()

            return {
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Failed to get clustering metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch clustering metrics"
        )


@router.get("/alert-context/{instance}")
async def get_alert_context(
    instance: str,
    metric: str = Query(default="cpu_usage", description="Metric name"),
    hours: int = Query(default=24, ge=1, le=168)
):
    """
    Get historical context metrics for an alert

    Args:
        instance: Instance that generated the alert
        metric: Metric to query (cpu_usage, memory_usage, disk_usage, etc.)
        hours: Hours of history (1-168)

    Returns:
        Time series data for the specified metric
    """
    settings = get_settings()

    if not settings.enable_prometheus_queries:
        raise HTTPException(
            status_code=503,
            detail="Prometheus queries are disabled"
        )

    try:
        async with PrometheusClient() as client:
            data = await client.get_alert_context_metrics(instance, metric, hours)

            return {
                "instance": instance,
                "metric": metric,
                "time_range_hours": hours,
                "data_points": len(data),
                "data": data
            }
    except Exception as e:
        logger.error(f"Failed to get alert context: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch alert context metrics"
        )


@router.post("/query")
async def execute_custom_query(
    query: str = Query(..., description="PromQL query"),
    time: Optional[str] = Query(None, description="Evaluation time (ISO format)")
):
    """
    Execute custom PromQL query (for advanced users)

    Args:
        query: PromQL query string
        time: Optional evaluation timestamp

    Returns:
        Raw Prometheus query result
    """
    settings = get_settings()

    if not settings.enable_prometheus_queries:
        raise HTTPException(
            status_code=503,
            detail="Prometheus queries are disabled"
        )

    try:
        eval_time = None
        if time:
            eval_time = datetime.fromisoformat(time)

        async with PrometheusClient() as client:
            result = await client.query(query, eval_time)

            return {
                "query": query,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
    except PrometheusQueryError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Query error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to execute query: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to execute query"
        )


@router.get("/targets")
async def get_prometheus_targets():
    """
    Get all Prometheus scrape targets

    Returns:
        Active and dropped targets with their status
    """
    settings = get_settings()

    if not settings.enable_prometheus_queries:
        raise HTTPException(
            status_code=503,
            detail="Prometheus queries are disabled"
        )

    try:
        async with PrometheusClient() as client:
            targets = await client.get_targets()

            active = targets.get("activeTargets", [])
            dropped = targets.get("droppedTargets", [])

            return {
                "active_count": len(active),
                "dropped_count": len(dropped),
                "active_targets": active,
                "dropped_targets": dropped
            }
    except Exception as e:
        logger.error(f"Failed to get targets: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch Prometheus targets"
        )
