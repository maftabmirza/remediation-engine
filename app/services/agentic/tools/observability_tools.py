"""
Observability Tools Module

Tools for querying metrics and logs from Prometheus/Grafana and Loki.
These tools enable the AI to gather real-time observability data.
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.services.agentic.tools import Tool, ToolParameter, ToolModule

logger = logging.getLogger(__name__)


class ObservabilityTools(ToolModule):
    """
    Observability tools for querying metrics and logs.
    
    These tools query external systems (Prometheus, Loki) and are
    useful for both Inquiry and Troubleshooting modes.
    """
    
    def _register_tools(self):
        """Register all observability tools"""
        
        # 1. Query Grafana Metrics
        self._register_tool(
            Tool(
                name="query_grafana_metrics",
                description="Query Prometheus metrics via Grafana. Use PromQL syntax. Returns metric values and trends.",
                parameters=[
                    ToolParameter(
                        name="promql",
                        type="string",
                        description="PromQL query (e.g., 'rate(http_requests_total[5m])')",
                        required=True
                    ),
                    ToolParameter(
                        name="time_range",
                        type="string",
                        description="Time range (e.g., '1h', '30m', '6h'). Default '1h'",
                        required=False,
                        default="1h"
                    )
                ]
            ),
            self._query_grafana_metrics
        )

        # 2. Query Grafana Logs
        self._register_tool(
            Tool(
                name="query_grafana_logs",
                description="Search logs via Grafana/Loki. Use LogQL syntax. Returns recent log entries matching the query.",
                parameters=[
                    ToolParameter(
                        name="logql",
                        type="string",
                        description="LogQL query (e.g., '{job=\"api\"} |= \"error\"')",
                        required=True
                    ),
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum log entries to return (default 50)",
                        required=False,
                        default=50
                    ),
                    ToolParameter(
                        name="time_range",
                        type="string",
                        description="Time range (e.g., '1h', '30m'). Default '1h'",
                        required=False,
                        default="1h"
                    )
                ]
            ),
            self._query_grafana_logs
        )

    # ========== Tool Implementations ==========

    async def _query_grafana_metrics(self, args: Dict[str, Any]) -> str:
        """Query Prometheus metrics via Grafana"""
        from app.services.prometheus_service import PrometheusClient

        promql = args.get("promql", "")
        time_range = args.get("time_range", "1h")

        if not promql:
            return "Error: promql parameter is required"

        try:
            client = PrometheusClient()

            # Parse time range
            end_time = datetime.now()
            if time_range.endswith('m'):
                minutes = int(time_range[:-1])
                start_time = end_time - timedelta(minutes=minutes)
            elif time_range.endswith('h'):
                hours = int(time_range[:-1])
                start_time = end_time - timedelta(hours=hours)
            else:
                start_time = end_time - timedelta(hours=1)

            # Determine step
            delta = end_time - start_time
            if delta.total_seconds() <= 3600:
                step = "15s"
            elif delta.total_seconds() <= 21600:
                step = "1m"
            else:
                step = "5m"

            result = await client.query_range(
                promql=promql,
                start=start_time,
                end=end_time,
                step=step
            )

            if not result:
                return f"No data returned for query: {promql}"

            output = [f"Metrics query: `{promql}` (last {time_range})\n"]

            series_list = result.get("result", [])
            for series in series_list[:5]:  # Limit to 5 series
                metric = series.get("metric", {})
                values = series.get("values", [])

                metric_labels = ", ".join([f"{k}={v}" for k, v in metric.items()])
                output.append(f"**{metric_labels or 'metric'}**")

                if values:
                    # Show latest value and trend
                    latest = float(values[-1][1]) if values else 0
                    first = float(values[0][1]) if values else 0
                    trend = "↑" if latest > first else "↓" if latest < first else "→"
                    output.append(f"  Current: {latest:.4f} {trend}")
                    output.append(f"  Points: {len(values)}")
                output.append("")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Grafana metrics error: {e}")
            return f"Error querying metrics: {str(e)}"

    async def _query_grafana_logs(self, args: Dict[str, Any]) -> str:
        """Query logs via Grafana/Loki"""
        from app.services.loki_client import LokiClient

        logql = args.get("logql", "")
        limit = args.get("limit", 50)
        time_range = args.get("time_range", "1h")

        if not logql:
            return "Error: logql parameter is required"

        try:
            client = LokiClient()

            # Parse time range
            end_time = datetime.now()
            if time_range.endswith('m'):
                minutes = int(time_range[:-1])
                start_time = end_time - timedelta(minutes=minutes)
            elif time_range.endswith('h'):
                hours = int(time_range[:-1])
                start_time = end_time - timedelta(hours=hours)
            else:
                start_time = end_time - timedelta(hours=1)

            entries = await client.query_range(
                logql=logql,
                start=start_time,
                end=end_time,
                limit=limit
            )

            if not entries:
                return f"No logs found for query: {logql}"

            output = [f"Log query: `{logql}` (last {time_range}, showing {min(len(entries), limit)} entries)\n"]

            for entry in entries[:limit]:
                timestamp = entry.timestamp.strftime("%H:%M:%S") if entry.timestamp else "N/A"
                level = entry.labels.get("level", "")
                line = entry.line[:200] + "..." if len(entry.line) > 200 else entry.line
                output.append(f"[{timestamp}] {level}: {line}")

            return "\n".join(output)

        except Exception as e:
            logger.error(f"Grafana logs error: {e}")
            return f"Error querying logs: {str(e)}"
