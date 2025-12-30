"""
Prometheus Query Service

Provides methods to query Prometheus for metrics, time series data,
and infrastructure health information.

This enables the AIOps platform to fetch real-time and historical metrics
directly from Prometheus without requiring users to switch to Grafana.
"""
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)


class PrometheusClient:
    """Client for querying Prometheus API"""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        """
        Initialize Prometheus client

        Args:
            base_url: Prometheus server URL (default from config)
            timeout: HTTP request timeout in seconds
        """
        settings = get_settings()
        self.base_url = (base_url or settings.prometheus_url).rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        logger.info(f"Initialized PrometheusClient with base_url: {self.base_url}")

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # =========================================================================
    # Core Query Methods
    # =========================================================================

    async def query(self, promql: str, time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Execute instant query

        Args:
            promql: PromQL query string
            time: Optional evaluation timestamp (default: now)

        Returns:
            Query result in Prometheus API format

        Example:
            result = await client.query('up{job="prometheus"}')
        """
        url = f"{self.base_url}/api/v1/query"
        params = {"query": promql}

        if time:
            params["time"] = time.timestamp()

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                raise PrometheusQueryError(
                    f"Query failed: {data.get('error', 'unknown error')}"
                )

            return data.get("data", {})
        except httpx.HTTPError as e:
            logger.error(f"Prometheus query failed: {e}")
            raise PrometheusConnectionError(f"Failed to connect to Prometheus: {e}")

    async def query_range(
        self,
        promql: str,
        start: datetime,
        end: datetime,
        step: str = "15s"
    ) -> Dict[str, Any]:
        """
        Execute range query for time series data

        Args:
            promql: PromQL query string
            start: Range start time
            end: Range end time
            step: Query resolution step (e.g., "15s", "1m", "5m")

        Returns:
            Time series result in Prometheus API format

        Example:
            end = datetime.now()
            start = end - timedelta(hours=1)
            result = await client.query_range(
                'rate(http_requests_total[5m])',
                start,
                end,
                step="1m"
            )
        """
        url = f"{self.base_url}/api/v1/query_range"
        params = {
            "query": promql,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step
        }

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                raise PrometheusQueryError(
                    f"Range query failed: {data.get('error', 'unknown error')}"
                )

            return data.get("data", {})
        except httpx.HTTPError as e:
            logger.error(f"Prometheus range query failed: {e}")
            raise PrometheusConnectionError(f"Failed to connect to Prometheus: {e}")

    # =========================================================================
    # Metadata & Discovery
    # =========================================================================

    async def get_targets(self) -> List[Dict[str, Any]]:
        """
        Get scrape targets status

        Returns:
            List of active and dropped targets

        Example:
            targets = await client.get_targets()
            for target in targets['activeTargets']:
                print(f"{target['labels']['job']}: {target['health']}")
        """
        url = f"{self.base_url}/api/v1/targets"

        try:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                raise PrometheusQueryError("Failed to get targets")

            return data.get("data", {})
        except httpx.HTTPError as e:
            logger.error(f"Failed to get Prometheus targets: {e}")
            raise PrometheusConnectionError(f"Failed to connect to Prometheus: {e}")

    async def get_label_values(self, label: str) -> List[str]:
        """
        Get all values for a specific label

        Args:
            label: Label name (e.g., "instance", "job")

        Returns:
            List of label values
        """
        url = f"{self.base_url}/api/v1/label/{label}/values"

        try:
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                raise PrometheusQueryError(f"Failed to get values for label {label}")

            return data.get("data", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get label values: {e}")
            return []

    # =========================================================================
    # Alert-Specific Queries
    # =========================================================================

    async def get_alert_trends(self, hours: int = 24) -> List[Dict]:
        """
        Get alert volume trends from aiops_alerts_received_total metric

        Args:
            hours: Number of hours to look back

        Returns:
            List of {timestamp, value} points
        """
        end = datetime.now()
        start = end - timedelta(hours=hours)

        # Query alert rate over time
        # Use sum to aggregate across all severity/status labels
        query = 'sum(increase(aiops_alerts_received_total[1h]))'

        try:
            result = await self.query_range(query, start, end, step="1h")
            return self._format_time_series(result)
        except Exception as e:
            logger.error(f"Failed to get alert trends: {e}")
            return []

    async def get_alert_rate_by_severity(self) -> Dict[str, float]:
        """
        Get current alert rate grouped by severity

        Returns:
            Dict mapping severity -> alerts per minute
        """
        query = 'sum(rate(aiops_alerts_received_total[5m])) by (severity) * 60'

        try:
            result = await self.query(query)

            rates = {}
            for item in result.get("result", []):
                severity = item["metric"].get("severity", "unknown")
                value = float(item["value"][1])
                rates[severity] = round(value, 2)

            return rates
        except Exception as e:
            logger.error(f"Failed to get alert rate by severity: {e}")
            return {}

    # =========================================================================
    # Infrastructure Metrics
    # =========================================================================

    async def get_infrastructure_metrics(self, instance: str) -> Dict[str, Optional[float]]:
        """
        Get CPU, memory, and disk usage for a specific instance

        Args:
            instance: Instance identifier (e.g., "server-01:9100")

        Returns:
            Dict with cpu_percent, memory_percent, disk_percent
        """
        queries = {
            "cpu": f'''100 - (avg by (instance) (rate(node_cpu_seconds_total{{mode="idle",instance="{instance}"}}[5m])) * 100)''',
            "memory": f'''(1 - (node_memory_MemAvailable_bytes{{instance="{instance}"}} / node_memory_MemTotal_bytes{{instance="{instance}"}})) * 100''',
            "disk": f'''(1 - (node_filesystem_avail_bytes{{instance="{instance}",mountpoint="/"}} / node_filesystem_size_bytes{{instance="{instance}",mountpoint="/"}})) * 100'''
        }

        results = {}
        for metric, query in queries.items():
            try:
                data = await self.query(query)
                results[f"{metric}_percent"] = self._parse_single_value(data)
            except Exception as e:
                logger.warning(f"Failed to get {metric} for {instance}: {e}")
                results[f"{metric}_percent"] = None

        return results

    async def get_all_instances_health(self) -> List[Dict[str, Any]]:
        """
        Get health metrics for all monitored instances

        Returns:
            List of instance health data
        """
        try:
            targets_data = await self.get_targets()
            active_targets = targets_data.get("activeTargets", [])

            instances = []
            seen_instances = set()

            for target in active_targets:
                instance = target["labels"].get("instance")
                if not instance or instance in seen_instances:
                    continue

                seen_instances.add(instance)

                # Get metrics for this instance
                metrics = await self.get_infrastructure_metrics(instance)

                instances.append({
                    "instance": instance,
                    "job": target["labels"].get("job", "unknown"),
                    "status": target.get("health", "unknown"),
                    "last_scrape": target.get("lastScrape"),
                    "scrape_duration": target.get("lastScrapeDuration"),
                    **metrics
                })

            return instances
        except Exception as e:
            logger.error(f"Failed to get instance health: {e}")
            return []

    # =========================================================================
    # Alert Context Enrichment
    # =========================================================================

    async def get_alert_context_metrics(
        self,
        instance: str,
        metric_name: str,
        hours: int = 24
    ) -> List[Dict]:
        """
        Get historical context for a specific metric related to an alert

        Args:
            instance: Instance that generated the alert
            metric_name: Metric to query (e.g., "cpu_usage", "memory_usage")
            hours: Hours of history to fetch

        Returns:
            Time series data for the metric
        """
        end = datetime.now()
        start = end - timedelta(hours=hours)

        # Map common metric names to PromQL queries
        metric_queries = {
            "cpu_usage": f'100 - (avg by (instance) (rate(node_cpu_seconds_total{{mode="idle",instance="{instance}"}}[5m])) * 100)',
            "memory_usage": f'(1 - (node_memory_MemAvailable_bytes{{instance="{instance}"}} / node_memory_MemTotal_bytes{{instance="{instance}"}})) * 100',
            "disk_usage": f'(1 - (node_filesystem_avail_bytes{{instance="{instance}",mountpoint="/"}} / node_filesystem_size_bytes{{instance="{instance}",mountpoint="/"}})) * 100',
            "network_in": f'rate(node_network_receive_bytes_total{{instance="{instance}"}}[5m])',
            "network_out": f'rate(node_network_transmit_bytes_total{{instance="{instance}"}}[5m])',
        }

        query = metric_queries.get(metric_name)
        if not query:
            logger.warning(f"Unknown metric name: {metric_name}")
            return []

        try:
            result = await self.query_range(query, start, end, step="5m")
            return self._format_time_series(result)
        except Exception as e:
            logger.error(f"Failed to get context metrics: {e}")
            return []

    # =========================================================================
    # AIOps Platform Metrics
    # =========================================================================

    async def get_platform_metrics(self) -> Dict[str, Any]:
        """
        Get metrics about the AIOps platform itself

        Returns:
            Platform health and usage metrics
        """
        queries = {
            "total_alerts_24h": 'sum(increase(aiops_alerts_received_total[24h]))',
            "alert_rate_5m": 'sum(rate(aiops_alerts_received_total[5m])) * 60',
            "llm_success_rate": '(sum(rate(aiops_llm_requests_total{status="success"}[5m])) / sum(rate(aiops_llm_requests_total[5m]))) * 100',
            "avg_llm_duration": 'avg(rate(aiops_llm_duration_seconds_sum[5m]) / rate(aiops_llm_duration_seconds_count[5m]))',
            "active_terminal_sessions": 'aiops_terminal_sessions_active',
            "webhook_success_rate": '(sum(rate(aiops_webhook_requests_total[5m])) - sum(rate(aiops_http_requests_total{endpoint="/webhook/alerts",status_code!~"2.."}[5m]))) / sum(rate(aiops_webhook_requests_total[5m])) * 100',
        }

        metrics = {}
        for name, query in queries.items():
            try:
                result = await self.query(query)
                metrics[name] = self._parse_single_value(result)
            except Exception as e:
                logger.warning(f"Failed to get platform metric {name}: {e}")
                metrics[name] = None

        return metrics

    async def get_clustering_metrics(self) -> Dict[str, Any]:
        """
        Get alert clustering performance metrics

        Returns:
            Clustering stats from Prometheus
        """
        queries = {
            "active_clusters": 'aiops_active_clusters',
            "noise_reduction_pct": 'aiops_noise_reduction_percent',
            "clusters_created_24h": 'sum(increase(aiops_clusters_created_total[24h]))',
            "alerts_clustered_24h": 'sum(increase(aiops_alerts_clustered_total[24h]))',
            "avg_clustering_duration": 'avg(rate(aiops_clustering_duration_seconds_sum[5m]) / rate(aiops_clustering_duration_seconds_count[5m]))',
        }

        metrics = {}
        for name, query in queries.items():
            try:
                result = await self.query(query)
                metrics[name] = self._parse_single_value(result)
            except Exception as e:
                logger.warning(f"Failed to get clustering metric {name}: {e}")
                metrics[name] = None

        return metrics

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_single_value(self, query_result: Dict[str, Any]) -> Optional[float]:
        """
        Extract single numeric value from Prometheus query result

        Args:
            query_result: Result from query() method

        Returns:
            Numeric value or None
        """
        try:
            results = query_result.get("result", [])
            if not results:
                return None

            # Get first result's value
            value = results[0].get("value", [None, None])
            if len(value) >= 2:
                return round(float(value[1]), 2)

            return None
        except (IndexError, ValueError, TypeError) as e:
            logger.debug(f"Failed to parse single value: {e}")
            return None

    def _format_time_series(self, range_result: Dict[str, Any]) -> List[Dict]:
        """
        Format range query result into simplified time series

        Args:
            range_result: Result from query_range() method

        Returns:
            List of {timestamp, value} dictionaries
        """
        try:
            results = range_result.get("result", [])
            if not results:
                return []

            # Take first result (or sum multiple series if needed)
            values = results[0].get("values", [])

            formatted = []
            for timestamp, value in values:
                formatted.append({
                    "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
                    "value": round(float(value), 2)
                })

            return formatted
        except Exception as e:
            logger.error(f"Failed to format time series: {e}")
            return []


# =============================================================================
# Custom Exceptions
# =============================================================================

class PrometheusError(Exception):
    """Base exception for Prometheus client errors"""
    pass


class PrometheusConnectionError(PrometheusError):
    """Raised when connection to Prometheus fails"""
    pass


class PrometheusQueryError(PrometheusError):
    """Raised when a query fails"""
    pass
