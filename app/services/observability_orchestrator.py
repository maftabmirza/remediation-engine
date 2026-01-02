"""
Observability Query Orchestrator

Orchestrates queries across multiple observability backends:
- Loki for logs
- Tempo for traces
- Prometheus/Mimir for metrics

Executes queries in parallel and aggregates results into a unified response.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import asyncio
import logging

from app.services.query_intent_parser import QueryIntent, get_intent_parser
from app.services.query_translator import QueryTranslationResult, TranslatedQuery, get_query_translator
from app.services.loki_client import LokiClient, LogEntry
from app.services.tempo_client import TempoClient, Trace, TraceSearchResult
from app.services.prometheus_service import PrometheusClient

logger = logging.getLogger(__name__)


class LogsResult(BaseModel):
    """Results from Loki log queries"""
    entries: List[LogEntry] = []
    total_count: int = 0
    query: str
    time_range: str


class TracesResult(BaseModel):
    """Results from Tempo trace queries"""
    traces: List[TraceSearchResult] = []
    total_count: int = 0
    query: str
    time_range: str


class MetricsResult(BaseModel):
    """Results from Prometheus metrics queries"""
    metric_name: str
    query: str
    value: Optional[float] = None
    values: List[Dict[str, Any]] = []
    time_range: str


class ObservabilityQueryResult(BaseModel):
    """Unified result from observability query"""
    # Original query
    original_query: str
    intent: QueryIntent

    # Results from each backend
    logs_results: List[LogsResult] = []
    traces_results: List[TracesResult] = []
    metrics_results: List[MetricsResult] = []

    # Summary
    total_logs: int = 0
    total_traces: int = 0
    total_metrics: int = 0

    # Execution metadata
    execution_time_ms: float = 0
    backends_queried: List[str] = []
    errors: List[str] = []


class ObservabilityOrchestrator:
    """
    Orchestrates observability queries across multiple backends.

    Parses natural language queries, translates to specific query languages,
    executes queries in parallel, and aggregates results.
    """

    def __init__(
        self,
        loki_client: Optional[LokiClient] = None,
        tempo_client: Optional[TempoClient] = None,
        prometheus_service: Optional[PrometheusClient] = None
    ):
        """
        Initialize orchestrator with observability clients.

        Args:
            loki_client: Loki client instance (or None to create default)
            tempo_client: Tempo client instance (or None to create default)
            prometheus_service: Prometheus service instance (or None to create default)
        """
        self.loki_client = loki_client or LokiClient()
        self.tempo_client = tempo_client or TempoClient()
        self.prometheus_service = prometheus_service or PrometheusClient()

        self.intent_parser = get_intent_parser()
        self.query_translator = get_query_translator()

    async def query(
        self,
        natural_language_query: str,
        app_context: Optional[Dict[str, Any]] = None
    ) -> ObservabilityQueryResult:
        """
        Execute a natural language observability query.

        Args:
            natural_language_query: Natural language query string
            app_context: Optional application context for query translation

        Returns:
            ObservabilityQueryResult with aggregated results
        """
        start_time = datetime.now()

        # Parse query intent
        intent = self.intent_parser.parse(natural_language_query)

        # Translate to specific query languages
        translation = self.query_translator.translate(intent, app_context)

        # Initialize result
        result = ObservabilityQueryResult(
            original_query=natural_language_query,
            intent=intent
        )

        # Execute queries in parallel
        tasks = []

        if translation.logql_queries:
            result.backends_queried.append("loki")
            for logql_query in translation.logql_queries:
                tasks.append(self._execute_loki_query(logql_query))

        if translation.traceql_queries:
            result.backends_queried.append("tempo")
            for traceql_query in translation.traceql_queries:
                tasks.append(self._execute_tempo_query(traceql_query))

        if translation.promql_queries:
            result.backends_queried.append("prometheus")
            for promql_query in translation.promql_queries:
                tasks.append(self._execute_prometheus_query(promql_query))

        # Execute all queries concurrently
        if tasks:
            backend_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Aggregate results
            for backend_result in backend_results:
                if isinstance(backend_result, Exception):
                    result.errors.append(str(backend_result))
                    logger.error(f"Query execution error: {backend_result}")
                elif isinstance(backend_result, LogsResult):
                    result.logs_results.append(backend_result)
                    result.total_logs += backend_result.total_count
                elif isinstance(backend_result, TracesResult):
                    result.traces_results.append(backend_result)
                    result.total_traces += backend_result.total_count
                elif isinstance(backend_result, MetricsResult):
                    result.metrics_results.append(backend_result)
                    result.total_metrics += 1

        # Calculate execution time
        end_time = datetime.now()
        result.execution_time_ms = (end_time - start_time).total_seconds() * 1000

        logger.info(
            f"Query executed in {result.execution_time_ms:.2f}ms: "
            f"{result.total_logs} logs, {result.total_traces} traces, "
            f"{result.total_metrics} metrics"
        )

        return result

    async def _execute_loki_query(self, query: TranslatedQuery) -> LogsResult:
        """Execute a LogQL query against Loki."""
        try:
            # Calculate time range
            start_time, end_time = self._calculate_time_range(
                query.time_range,
                query.start_time,
                query.end_time
            )

            # Execute query
            if start_time and end_time:
                entries = await self.loki_client.query_range(
                    query.query,
                    start=start_time,
                    end=end_time,
                    limit=query.limit
                )
            else:
                entries = await self.loki_client.query(
                    query.query,
                    limit=query.limit
                )

            return LogsResult(
                entries=entries,
                total_count=len(entries),
                query=query.query,
                time_range=query.time_range
            )

        except Exception as e:
            logger.error(f"Loki query failed: {e}")
            raise

    async def _execute_tempo_query(self, query: TranslatedQuery) -> TracesResult:
        """Execute a TraceQL query against Tempo."""
        try:
            # Calculate time range
            start_time, end_time = self._calculate_time_range(
                query.time_range,
                query.start_time,
                query.end_time
            )

            # Parse TraceQL query to extract tags
            # For simplicity, we'll use search_traces with parsed conditions
            tags = self._parse_traceql_tags(query.query)

            # Execute search
            traces = await self.tempo_client.search_traces(
                tags=tags,
                start=start_time,
                end=end_time,
                limit=query.limit
            )

            return TracesResult(
                traces=traces,
                total_count=len(traces),
                query=query.query,
                time_range=query.time_range
            )

        except Exception as e:
            logger.error(f"Tempo query failed: {e}")
            raise

    async def _execute_prometheus_query(self, query: TranslatedQuery) -> MetricsResult:
        """Execute a PromQL query against Prometheus."""
        try:
            # Calculate time range
            start_time, end_time = self._calculate_time_range(
                query.time_range,
                query.start_time,
                query.end_time
            )

            # Execute range query
            result_data = await self.prometheus_service.query_range(
                query=query.query,
                start=start_time,
                end=end_time,
                step=self._calculate_step(query.time_range)
            )

            # Extract metric name from query
            metric_name = self._extract_metric_name(query.query)

            # Parse result
            value = None
            values = []

            if result_data and len(result_data) > 0:
                # Get the most recent value
                first_result = result_data[0]
                if "values" in first_result and len(first_result["values"]) > 0:
                    # Get last value in time series
                    last_value = first_result["values"][-1]
                    value = float(last_value[1])
                    values = [
                        {"timestamp": v[0], "value": float(v[1])}
                        for v in first_result["values"]
                    ]

            return MetricsResult(
                metric_name=metric_name,
                query=query.query,
                value=value,
                values=values,
                time_range=query.time_range
            )

        except Exception as e:
            logger.error(f"Prometheus query failed: {e}")
            raise

    def _calculate_time_range(
        self,
        time_range: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime]
    ) -> "tuple[datetime, datetime]":
        """Calculate start and end time from time range string."""
        if start_time and end_time:
            return start_time, end_time

        # Parse time range string (e.g., "1h", "24h", "7d")
        end = datetime.now()

        if time_range.endswith('s'):
            seconds = int(time_range[:-1])
            start = end - timedelta(seconds=seconds)
        elif time_range.endswith('m'):
            minutes = int(time_range[:-1])
            start = end - timedelta(minutes=minutes)
        elif time_range.endswith('h'):
            hours = int(time_range[:-1])
            start = end - timedelta(hours=hours)
        elif time_range.endswith('d'):
            days = int(time_range[:-1])
            start = end - timedelta(days=days)
        elif time_range.endswith('w'):
            weeks = int(time_range[:-1])
            start = end - timedelta(weeks=weeks)
        else:
            # Default to 1 hour
            start = end - timedelta(hours=1)

        return start, end

    def _calculate_step(self, time_range: str) -> str:
        """Calculate appropriate step size for Prometheus range query."""
        # Extract duration in hours
        if time_range.endswith('h'):
            hours = int(time_range[:-1])
        elif time_range.endswith('d'):
            hours = int(time_range[:-1]) * 24
        elif time_range.endswith('w'):
            hours = int(time_range[:-1]) * 24 * 7
        elif time_range.endswith('m'):
            hours = int(time_range[:-1]) / 60
        else:
            hours = 1

        # Choose appropriate step
        if hours <= 1:
            return "15s"
        elif hours <= 6:
            return "1m"
        elif hours <= 24:
            return "5m"
        elif hours <= 168:  # 1 week
            return "1h"
        else:
            return "1d"

    def _parse_traceql_tags(self, traceql: str) -> Dict[str, str]:
        """Parse TraceQL query to extract tag filters."""
        import re

        tags = {}

        # Extract tag=value patterns
        # Example: {resource.service.name="api" && http.status_code=500}
        patterns = re.findall(r'([\w.]+)="([^"]+)"', traceql)
        for key, value in patterns:
            tags[key] = value

        # Extract tag=number patterns
        patterns = re.findall(r'([\w.]+)=(\d+)', traceql)
        for key, value in patterns:
            tags[key] = value

        return tags

    def _extract_metric_name(self, promql: str) -> str:
        """Extract metric name from PromQL query."""
        import re

        # Try to extract first metric name
        match = re.search(r'([a-zA-Z_:][a-zA-Z0-9_:]*)', promql)
        if match:
            return match.group(1)

        return "metric"


# Global orchestrator instance
_orchestrator: Optional[ObservabilityOrchestrator] = None


def get_observability_orchestrator() -> ObservabilityOrchestrator:
    """
    Get global observability orchestrator instance.

    Returns:
        Singleton ObservabilityOrchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ObservabilityOrchestrator()
    return _orchestrator
