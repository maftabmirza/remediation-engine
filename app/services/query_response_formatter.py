"""
Query Response Formatter

Formats observability query results into human-readable summaries.
Converts raw logs, traces, and metrics into structured insights.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel
import logging

from app.services.observability_orchestrator import ObservabilityQueryResult

logger = logging.getLogger(__name__)


class FormattedInsight(BaseModel):
    """A formatted insight from observability data"""
    title: str
    summary: str
    details: List[str] = []
    severity: str = "info"  # info, warning, error, critical
    metric_value: Optional[float] = None
    trend: Optional[str] = None  # up, down, stable


class FormattedResponse(BaseModel):
    """Formatted response with human-readable insights"""
    query: str
    intent_type: str

    # Executive summary
    summary: str

    # Key insights
    insights: List[FormattedInsight] = []

    # Quick stats
    stats: Dict[str, Any] = {}

    # Recommendations
    recommendations: List[str] = []

    # Raw data available
    has_logs: bool = False
    has_traces: bool = False
    has_metrics: bool = False

    execution_time_ms: float = 0


class QueryResponseFormatter:
    """
    Formats observability query results into human-readable responses.

    Analyzes query results to extract insights, trends, and recommendations.
    """

    def format(self, result: ObservabilityQueryResult) -> FormattedResponse:
        """
        Format query result into human-readable response.

        Args:
            result: Raw query result from orchestrator

        Returns:
            FormattedResponse with insights and recommendations
        """
        formatted = FormattedResponse(
            query=result.original_query,
            intent_type=result.intent.intent_type,
            summary="",
            execution_time_ms=result.execution_time_ms,
            has_logs=(result.total_logs > 0),
            has_traces=(result.total_traces > 0),
            has_metrics=(result.total_metrics > 0)
        )

        # Generate summary and insights based on intent type
        if result.intent.intent_type == "errors":
            self._format_errors(result, formatted)
        elif result.intent.intent_type == "performance":
            self._format_performance(result, formatted)
        elif result.intent.intent_type == "health":
            self._format_health(result, formatted)
        elif result.intent.intent_type == "logs":
            self._format_logs(result, formatted)
        elif result.intent.intent_type == "traces":
            self._format_traces(result, formatted)
        elif result.intent.intent_type == "metrics":
            self._format_metrics(result, formatted)
        else:
            self._format_generic(result, formatted)

        # Add execution stats
        formatted.stats["execution_time_ms"] = result.execution_time_ms
        formatted.stats["backends_queried"] = result.backends_queried
        formatted.stats["total_data_points"] = (
            result.total_logs + result.total_traces + result.total_metrics
        )

        return formatted

    def _format_errors(self, result: ObservabilityQueryResult, formatted: FormattedResponse):
        """Format error analysis results."""
        total_errors = result.total_logs

        if total_errors == 0:
            formatted.summary = "✅ No errors found in the specified time range."
            formatted.insights.append(FormattedInsight(
                title="Error Status",
                summary="System is operating normally with no errors detected.",
                severity="info"
            ))
        else:
            formatted.summary = f"⚠️ Found {total_errors} error{'s' if total_errors > 1 else ''} in the time range."

            # Error count insight
            formatted.insights.append(FormattedInsight(
                title="Error Count",
                summary=f"{total_errors} error entries detected",
                severity="error" if total_errors > 10 else "warning",
                metric_value=float(total_errors)
            ))

            # Sample error logs
            if result.logs_results and len(result.logs_results) > 0:
                log_result = result.logs_results[0]
                sample_errors = log_result.entries[:5]  # First 5 errors

                error_details = []
                for entry in sample_errors:
                    timestamp = entry.timestamp
                    line = entry.line[:100]  # Truncate long lines
                    error_details.append(f"[{timestamp}] {line}")

                formatted.insights.append(FormattedInsight(
                    title="Sample Errors",
                    summary=f"Showing {len(sample_errors)} most recent errors",
                    details=error_details,
                    severity="warning"
                ))

            # Check metrics for error rate
            if result.metrics_results:
                for metric in result.metrics_results:
                    if metric.value is not None:
                        formatted.insights.append(FormattedInsight(
                            title="Error Rate",
                            summary=f"Current error rate: {metric.value:.4f} errors/sec",
                            metric_value=metric.value,
                            severity="error" if metric.value > 0.1 else "warning"
                        ))

            # Recommendations
            formatted.recommendations.append("Review error logs to identify root causes")
            formatted.recommendations.append("Check if errors correlate with recent deployments")
            if total_errors > 100:
                formatted.recommendations.append("High error volume detected - investigate urgently")

    def _format_performance(self, result: ObservabilityQueryResult, formatted: FormattedResponse):
        """Format performance analysis results."""
        if not result.metrics_results:
            formatted.summary = "No performance metrics available for the time range."
            return

        # Analyze latency metrics
        latency_metrics = []
        for metric in result.metrics_results:
            if "latency" in metric.metric_name.lower() or "duration" in metric.metric_name.lower():
                latency_metrics.append(metric)

        if latency_metrics:
            p95_metric = latency_metrics[0]  # Assume first is P95

            if p95_metric.value is not None:
                latency_ms = p95_metric.value * 1000  # Convert to ms

                # Determine severity
                if latency_ms < 100:
                    severity = "info"
                    status = "✅ Excellent"
                elif latency_ms < 500:
                    severity = "info"
                    status = "✅ Good"
                elif latency_ms < 1000:
                    severity = "warning"
                    status = "⚠️ Acceptable"
                else:
                    severity = "error"
                    status = "❌ Poor"

                formatted.summary = f"{status} - P95 latency is {latency_ms:.1f}ms"

                formatted.insights.append(FormattedInsight(
                    title="Latency Performance",
                    summary=f"95th percentile response time: {latency_ms:.1f}ms",
                    metric_value=latency_ms,
                    severity=severity
                ))

                # Recommendations based on latency
                if latency_ms > 500:
                    formatted.recommendations.append("Consider optimizing slow database queries")
                    formatted.recommendations.append("Review caching strategy")
                if latency_ms > 1000:
                    formatted.recommendations.append("High latency detected - investigate performance bottlenecks")
        else:
            formatted.summary = "Performance metrics analyzed - no latency data available."

    def _format_health(self, result: ObservabilityQueryResult, formatted: FormattedResponse):
        """Format health check results."""
        if not result.metrics_results:
            formatted.summary = "Unable to determine health status - no metrics available."
            return

        # Check for 'up' metric
        is_up = False
        success_rate = None

        for metric in result.metrics_results:
            if "up" in metric.query.lower():
                is_up = (metric.value == 1.0) if metric.value is not None else False
            elif "success" in metric.metric_name.lower() or "success" in metric.query.lower():
                success_rate = metric.value

        if is_up:
            formatted.summary = "✅ Application is healthy and running."
            formatted.insights.append(FormattedInsight(
                title="Service Status",
                summary="Service is up and responding",
                severity="info"
            ))
        else:
            formatted.summary = "❌ Application appears to be down or unhealthy."
            formatted.insights.append(FormattedInsight(
                title="Service Status",
                summary="Service may be down or not responding",
                severity="critical"
            ))
            formatted.recommendations.append("Check service logs for errors")
            formatted.recommendations.append("Verify service deployment status")

        if success_rate is not None:
            success_pct = success_rate * 100

            if success_pct >= 99.9:
                severity = "info"
                status = "✅ Excellent"
            elif success_pct >= 99.0:
                severity = "info"
                status = "✅ Good"
            elif success_pct >= 95.0:
                severity = "warning"
                status = "⚠️ Acceptable"
            else:
                severity = "error"
                status = "❌ Poor"

            formatted.insights.append(FormattedInsight(
                title="Success Rate",
                summary=f"{status} - {success_pct:.2f}% of requests successful",
                metric_value=success_pct,
                severity=severity
            ))

    def _format_logs(self, result: ObservabilityQueryResult, formatted: FormattedResponse):
        """Format log query results."""
        total_logs = result.total_logs

        if total_logs == 0:
            formatted.summary = "No logs found matching the query criteria."
        else:
            formatted.summary = f"Found {total_logs} log entries in the time range."

            formatted.insights.append(FormattedInsight(
                title="Log Count",
                summary=f"{total_logs} log entries matched the query",
                metric_value=float(total_logs),
                severity="info"
            ))

            # Show sample logs
            if result.logs_results and len(result.logs_results) > 0:
                log_result = result.logs_results[0]
                sample_logs = log_result.entries[:10]

                log_details = []
                for entry in sample_logs:
                    line = entry.line[:100]
                    log_details.append(f"{line}")

                formatted.insights.append(FormattedInsight(
                    title="Sample Log Entries",
                    summary=f"Showing {len(sample_logs)} most recent entries",
                    details=log_details,
                    severity="info"
                ))

    def _format_traces(self, result: ObservabilityQueryResult, formatted: FormattedResponse):
        """Format trace query results."""
        total_traces = result.total_traces

        if total_traces == 0:
            formatted.summary = "No traces found matching the query criteria."
        else:
            formatted.summary = f"Found {total_traces} trace{'s' if total_traces > 1 else ''} in the time range."

            formatted.insights.append(FormattedInsight(
                title="Trace Count",
                summary=f"{total_traces} distributed traces found",
                metric_value=float(total_traces),
                severity="info"
            ))

            # Analyze trace durations
            if result.traces_results and len(result.traces_results) > 0:
                trace_result = result.traces_results[0]

                if trace_result.traces:
                    durations = [t.duration_ms for t in trace_result.traces]
                    avg_duration = sum(durations) / len(durations)
                    max_duration = max(durations)

                    formatted.insights.append(FormattedInsight(
                        title="Trace Duration",
                        summary=f"Average: {avg_duration:.1f}ms, Max: {max_duration:.1f}ms",
                        metric_value=avg_duration,
                        severity="warning" if avg_duration > 1000 else "info"
                    ))

                    # Show sample traces
                    sample_traces = trace_result.traces[:5]
                    trace_details = []
                    for trace in sample_traces:
                        trace_details.append(
                            f"{trace.root_service_name} - {trace.root_trace_name} ({trace.duration_ms}ms)"
                        )

                    formatted.insights.append(FormattedInsight(
                        title="Sample Traces",
                        summary=f"Showing {len(sample_traces)} traces",
                        details=trace_details,
                        severity="info"
                    ))

    def _format_metrics(self, result: ObservabilityQueryResult, formatted: FormattedResponse):
        """Format metrics query results."""
        total_metrics = result.total_metrics

        if total_metrics == 0:
            formatted.summary = "No metrics data available for the query."
        else:
            formatted.summary = f"Retrieved {total_metrics} metric{'s' if total_metrics > 1 else ''}."

            for metric in result.metrics_results:
                if metric.value is not None:
                    formatted.insights.append(FormattedInsight(
                        title=metric.metric_name.replace('_', ' ').title(),
                        summary=f"Current value: {metric.value:.4f}",
                        metric_value=metric.value,
                        severity="info"
                    ))

    def _format_generic(self, result: ObservabilityQueryResult, formatted: FormattedResponse):
        """Format generic query results."""
        data_sources = []
        if result.total_logs > 0:
            data_sources.append(f"{result.total_logs} logs")
        if result.total_traces > 0:
            data_sources.append(f"{result.total_traces} traces")
        if result.total_metrics > 0:
            data_sources.append(f"{result.total_metrics} metrics")

        if data_sources:
            formatted.summary = f"Found: {', '.join(data_sources)}"
        else:
            formatted.summary = "No data found matching the query."


# Global formatter instance
_formatter: Optional[QueryResponseFormatter] = None


def get_response_formatter() -> QueryResponseFormatter:
    """
    Get global query response formatter instance.

    Returns:
        Singleton QueryResponseFormatter instance
    """
    global _formatter
    if _formatter is None:
        _formatter = QueryResponseFormatter()
    return _formatter
