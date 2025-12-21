"""
Prometheus Integration API

Provides endpoints to query Prometheus metrics and expose them
in the AIOps platform UI, eliminating the need to use Grafana separately.
"""
from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
from pydantic import BaseModel, Field

from app.services.prometheus_service import (
    PrometheusClient,
    PrometheusConnectionError,
    PrometheusQueryError
)
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prometheus", tags=["Prometheus"])


# Configuration Models
class PrometheusConfig(BaseModel):
    """Prometheus integration configuration"""
    prometheus_url: str = Field(..., description="Prometheus server URL")
    enable_prometheus_queries: bool = Field(True, description="Enable Prometheus queries")
    prometheus_timeout: int = Field(30, description="Request timeout in seconds", ge=5, le=300)

    prometheus_dashboard_enabled: bool = Field(True, description="Show Prometheus dashboard section")
    prometheus_refresh_interval: int = Field(30, description="Dashboard refresh interval (seconds)", ge=10, le=300)
    prometheus_default_time_range: str = Field("24h", description="Default time range")

    infrastructure_metrics_enabled: bool = Field(True, description="Show infrastructure metrics")
    infrastructure_show_cpu: bool = Field(True, description="Show CPU metrics")
    infrastructure_show_memory: bool = Field(True, description="Show memory metrics")
    infrastructure_show_disk: bool = Field(True, description="Show disk metrics")
    infrastructure_cpu_warning_threshold: int = Field(75, ge=0, le=100)
    infrastructure_cpu_critical_threshold: int = Field(90, ge=0, le=100)
    infrastructure_memory_warning_threshold: int = Field(75, ge=0, le=100)
    infrastructure_memory_critical_threshold: int = Field(90, ge=0, le=100)
    infrastructure_disk_warning_threshold: int = Field(75, ge=0, le=100)
    infrastructure_disk_critical_threshold: int = Field(90, ge=0, le=100)

    chart_library: str = Field("echarts", description="Chart library to use")
    chart_theme: str = Field("grafana-dark", description="Chart theme")
    chart_enable_zoom: bool = Field(True, description="Enable chart zoom")
    chart_enable_animations: bool = Field(True, description="Enable chart animations")
    chart_max_data_points: int = Field(1000, description="Max data points per chart", ge=100, le=10000)

    alert_trends_enabled: bool = Field(True, description="Show alert trends")
    alert_trends_default_hours: int = Field(24, description="Default hours for trends", ge=1, le=168)
    alert_trends_step: str = Field("1h", description="Query step size")

    prometheus_use_cache: bool = Field(True, description="Enable query caching")
    prometheus_cache_ttl: int = Field(60, description="Cache TTL in seconds", ge=10, le=3600)
    prometheus_max_retries: int = Field(3, description="Max retry attempts", ge=0, le=10)
    prometheus_retry_delay: int = Field(2, description="Retry delay in seconds", ge=1, le=60)


@router.get("/config")
async def get_prometheus_config() -> PrometheusConfig:
    """
    Get current Prometheus integration configuration

    Returns all configurable settings for Prometheus integration
    """
    settings = get_settings()

    return PrometheusConfig(
        prometheus_url=settings.prometheus_url,
        enable_prometheus_queries=settings.enable_prometheus_queries,
        prometheus_timeout=settings.prometheus_timeout,
        prometheus_dashboard_enabled=settings.prometheus_dashboard_enabled,
        prometheus_refresh_interval=settings.prometheus_refresh_interval,
        prometheus_default_time_range=settings.prometheus_default_time_range,
        infrastructure_metrics_enabled=settings.infrastructure_metrics_enabled,
        infrastructure_show_cpu=settings.infrastructure_show_cpu,
        infrastructure_show_memory=settings.infrastructure_show_memory,
        infrastructure_show_disk=settings.infrastructure_show_disk,
        infrastructure_cpu_warning_threshold=settings.infrastructure_cpu_warning_threshold,
        infrastructure_cpu_critical_threshold=settings.infrastructure_cpu_critical_threshold,
        infrastructure_memory_warning_threshold=settings.infrastructure_memory_warning_threshold,
        infrastructure_memory_critical_threshold=settings.infrastructure_memory_critical_threshold,
        infrastructure_disk_warning_threshold=settings.infrastructure_disk_warning_threshold,
        infrastructure_disk_critical_threshold=settings.infrastructure_disk_critical_threshold,
        chart_library=settings.chart_library,
        chart_theme=settings.chart_theme,
        chart_enable_zoom=settings.chart_enable_zoom,
        chart_enable_animations=settings.chart_enable_animations,
        chart_max_data_points=settings.chart_max_data_points,
        alert_trends_enabled=settings.alert_trends_enabled,
        alert_trends_default_hours=settings.alert_trends_default_hours,
        alert_trends_step=settings.alert_trends_step,
        prometheus_use_cache=settings.prometheus_use_cache,
        prometheus_cache_ttl=settings.prometheus_cache_ttl,
        prometheus_max_retries=settings.prometheus_max_retries,
        prometheus_retry_delay=settings.prometheus_retry_delay,
    )


@router.put("/config")
async def update_prometheus_config(config: PrometheusConfig):
    """
    Update Prometheus integration configuration

    Note: Updates are written to environment variables and require app restart.
    For runtime config, use the settings page.
    """
    import os
    from pathlib import Path

    # Update .env file
    env_file = Path(".env")
    env_vars = {}

    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value

    # Update Prometheus settings
    env_vars['PROMETHEUS_URL'] = config.prometheus_url
    env_vars['ENABLE_PROMETHEUS_QUERIES'] = str(config.enable_prometheus_queries)
    env_vars['PROMETHEUS_TIMEOUT'] = str(config.prometheus_timeout)
    env_vars['PROMETHEUS_DASHBOARD_ENABLED'] = str(config.prometheus_dashboard_enabled)
    env_vars['PROMETHEUS_REFRESH_INTERVAL'] = str(config.prometheus_refresh_interval)
    env_vars['PROMETHEUS_DEFAULT_TIME_RANGE'] = config.prometheus_default_time_range
    env_vars['INFRASTRUCTURE_METRICS_ENABLED'] = str(config.infrastructure_metrics_enabled)
    env_vars['INFRASTRUCTURE_SHOW_CPU'] = str(config.infrastructure_show_cpu)
    env_vars['INFRASTRUCTURE_SHOW_MEMORY'] = str(config.infrastructure_show_memory)
    env_vars['INFRASTRUCTURE_SHOW_DISK'] = str(config.infrastructure_show_disk)
    env_vars['INFRASTRUCTURE_CPU_WARNING_THRESHOLD'] = str(config.infrastructure_cpu_warning_threshold)
    env_vars['INFRASTRUCTURE_CPU_CRITICAL_THRESHOLD'] = str(config.infrastructure_cpu_critical_threshold)
    env_vars['INFRASTRUCTURE_MEMORY_WARNING_THRESHOLD'] = str(config.infrastructure_memory_warning_threshold)
    env_vars['INFRASTRUCTURE_MEMORY_CRITICAL_THRESHOLD'] = str(config.infrastructure_memory_critical_threshold)
    env_vars['INFRASTRUCTURE_DISK_WARNING_THRESHOLD'] = str(config.infrastructure_disk_warning_threshold)
    env_vars['INFRASTRUCTURE_DISK_CRITICAL_THRESHOLD'] = str(config.infrastructure_disk_critical_threshold)
    env_vars['CHART_LIBRARY'] = config.chart_library
    env_vars['CHART_THEME'] = config.chart_theme
    env_vars['CHART_ENABLE_ZOOM'] = str(config.chart_enable_zoom)
    env_vars['CHART_ENABLE_ANIMATIONS'] = str(config.chart_enable_animations)
    env_vars['CHART_MAX_DATA_POINTS'] = str(config.chart_max_data_points)
    env_vars['ALERT_TRENDS_ENABLED'] = str(config.alert_trends_enabled)
    env_vars['ALERT_TRENDS_DEFAULT_HOURS'] = str(config.alert_trends_default_hours)
    env_vars['ALERT_TRENDS_STEP'] = config.alert_trends_step
    env_vars['PROMETHEUS_USE_CACHE'] = str(config.prometheus_use_cache)
    env_vars['PROMETHEUS_CACHE_TTL'] = str(config.prometheus_cache_ttl)
    env_vars['PROMETHEUS_MAX_RETRIES'] = str(config.prometheus_max_retries)
    env_vars['PROMETHEUS_RETRY_DELAY'] = str(config.prometheus_retry_delay)

    # Write back to .env
    with open(env_file, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    return {
        "message": "Configuration updated successfully. Restart the application for changes to take effect.",
        "config": config
    }


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
