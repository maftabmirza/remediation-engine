"""
Panel Template Seeder
Seeds common Prometheus panel templates on startup
"""
import logging
from sqlalchemy.orm import Session
from app.models_dashboards import PrometheusPanel, PrometheusDatasource
import uuid

logger = logging.getLogger(__name__)


COMMON_PANEL_TEMPLATES = [
    {
        "name": "CPU Usage by Instance",
        "description": "Shows CPU usage percentage for each instance",
        "promql_query": '100 - (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
        "legend_format": "{{instance}}",
        "panel_type": "graph",
        "time_range": "1h",
        "tags": ["infrastructure", "cpu", "monitoring"]
    },
    {
        "name": "Memory Usage",
        "description": "Memory usage in GB for each instance",
        "promql_query": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1024 / 1024 / 1024",
        "legend_format": "{{instance}}",
        "panel_type": "graph",
        "time_range": "1h",
        "tags": ["infrastructure", "memory", "monitoring"]
    },
    {
        "name": "Disk Usage Percentage",
        "description": "Disk usage percentage by mount point",
        "promql_query": '100 - ((node_filesystem_avail_bytes{mountpoint="/",fstype!="rootfs"} * 100) / node_filesystem_size_bytes{mountpoint="/",fstype!="rootfs"})',
        "legend_format": "{{instance}} - {{mountpoint}}",
        "panel_type": "gauge",
        "time_range": "1h",
        "tags": ["infrastructure", "disk", "monitoring"],
        "thresholds": {
            "warning": 75,
            "critical": 90
        }
    },
    {
        "name": "Network Traffic (Received)",
        "description": "Network receive rate in MB/s",
        "promql_query": "rate(node_network_receive_bytes_total[5m]) / 1024 / 1024",
        "legend_format": "{{instance}} - {{device}}",
        "panel_type": "graph",
        "time_range": "1h",
        "tags": ["infrastructure", "network", "monitoring"]
    },
    {
        "name": "Network Traffic (Transmitted)",
        "description": "Network transmit rate in MB/s",
        "promql_query": "rate(node_network_transmit_bytes_total[5m]) / 1024 / 1024",
        "legend_format": "{{instance}} - {{device}}",
        "panel_type": "graph",
        "time_range": "1h",
        "tags": ["infrastructure", "network", "monitoring"]
    },
    {
        "name": "HTTP Request Rate",
        "description": "HTTP requests per second",
        "promql_query": "sum(rate(http_requests_total[5m])) by (method, status)",
        "legend_format": "{{method}} {{status}}",
        "panel_type": "graph",
        "time_range": "1h",
        "tags": ["application", "http", "monitoring"]
    },
    {
        "name": "HTTP Error Rate",
        "description": "Percentage of HTTP 5xx errors",
        "promql_query": '(sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))) * 100',
        "legend_format": "Error Rate %",
        "panel_type": "stat",
        "time_range": "1h",
        "tags": ["application", "http", "errors"],
        "thresholds": {
            "warning": 1,
            "critical": 5
        }
    },
    {
        "name": "HTTP Request Duration (p95)",
        "description": "95th percentile request duration in seconds",
        "promql_query": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))',
        "legend_format": "p95",
        "panel_type": "graph",
        "time_range": "1h",
        "tags": ["application", "http", "latency"]
    },
    {
        "name": "Container CPU Usage",
        "description": "CPU usage per container",
        "promql_query": 'sum(rate(container_cpu_usage_seconds_total{container!=""}[5m])) by (container)',
        "legend_format": "{{container}}",
        "panel_type": "graph",
        "time_range": "1h",
        "tags": ["kubernetes", "containers", "cpu"]
    },
    {
        "name": "Container Memory Usage",
        "description": "Memory usage per container in MB",
        "promql_query": 'sum(container_memory_usage_bytes{container!=""}) by (container) / 1024 / 1024',
        "legend_format": "{{container}}",
        "panel_type": "graph",
        "time_range": "1h",
        "tags": ["kubernetes", "containers", "memory"]
    },
    {
        "name": "Pod Restarts",
        "description": "Number of pod restarts",
        "promql_query": "sum(kube_pod_container_status_restarts_total) by (pod)",
        "legend_format": "{{pod}}",
        "panel_type": "table",
        "time_range": "24h",
        "tags": ["kubernetes", "pods", "monitoring"]
    },
    {
        "name": "Database Connection Pool",
        "description": "Active database connections",
        "promql_query": "sum(pg_stat_activity_count) by (state)",
        "legend_format": "{{state}}",
        "panel_type": "graph",
        "time_range": "1h",
        "tags": ["database", "postgresql", "connections"]
    },
    {
        "name": "API Response Time",
        "description": "Average API response time by endpoint",
        "promql_query": "sum(rate(http_request_duration_seconds_sum[5m])) by (endpoint) / sum(rate(http_request_duration_seconds_count[5m])) by (endpoint)",
        "legend_format": "{{endpoint}}",
        "panel_type": "graph",
        "time_range": "1h",
        "tags": ["application", "api", "latency"]
    },
    {
        "name": "Active Alerts",
        "description": "Number of active Prometheus alerts",
        "promql_query": "ALERTS{alertstate='firing'}",
        "legend_format": "{{alertname}}",
        "panel_type": "stat",
        "time_range": "1h",
        "tags": ["alerting", "monitoring"]
    },
    {
        "name": "Up/Down Status",
        "description": "Target availability (1 = up, 0 = down)",
        "promql_query": "up",
        "legend_format": "{{instance}} - {{job}}",
        "panel_type": "gauge",
        "time_range": "1h",
        "tags": ["availability", "monitoring"]
    }
]


def seed_panel_templates(db: Session):
    """
    Seed common Prometheus panel templates
    Only creates templates that don't already exist
    """
    try:
        # Get default datasource
        default_datasource = db.query(PrometheusDatasource).filter(
            PrometheusDatasource.is_default == True
        ).first()

        if not default_datasource:
            logger.warning("No default Prometheus datasource found. Skipping panel template seeding.")
            return

        # Check which templates already exist
        existing_templates = db.query(PrometheusPanel).filter(
            PrometheusPanel.is_template == True
        ).all()

        existing_names = {t.name for t in existing_templates}

        # Seed new templates
        created_count = 0
        for template_data in COMMON_PANEL_TEMPLATES:
            if template_data["name"] in existing_names:
                continue

            panel = PrometheusPanel(
                id=str(uuid.uuid4()),
                name=template_data["name"],
                description=template_data.get("description"),
                datasource_id=default_datasource.id,
                promql_query=template_data["promql_query"],
                legend_format=template_data.get("legend_format"),
                panel_type=template_data["panel_type"],
                time_range=template_data.get("time_range", "1h"),
                refresh_interval=30,
                step="auto",
                is_template=True,
                is_public=True,
                tags=template_data.get("tags", []),
                thresholds=template_data.get("thresholds"),
                created_by="system"
            )

            db.add(panel)
            created_count += 1

        if created_count > 0:
            db.commit()
            logger.info(f"✅ Created {created_count} panel template(s)")
        else:
            logger.info("Panel templates already exist, skipping seeding")

    except Exception as e:
        logger.error(f"Failed to seed panel templates: {e}")
        db.rollback()
