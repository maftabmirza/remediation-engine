"""
Query Translator Service

Translates parsed query intents into specific query languages:
- LogQL for Loki log queries
- TraceQL for Tempo trace queries
- PromQL for Prometheus/Mimir metrics queries

Uses application context to generate targeted queries.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging

from app.services.query_intent_parser import QueryIntent

logger = logging.getLogger(__name__)


class TranslatedQuery(BaseModel):
    """A translated query in a specific query language"""
    query_language: str  # "logql", "traceql", "promql"
    query: str
    time_range: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 100


class QueryTranslationResult(BaseModel):
    """Result of query translation containing queries for all relevant backends"""
    logql_queries: List[TranslatedQuery] = []
    traceql_queries: List[TranslatedQuery] = []
    promql_queries: List[TranslatedQuery] = []
    intent: QueryIntent


class QueryTranslator:
    """
    Translates query intents into observability query languages.

    Generates LogQL, TraceQL, and PromQL queries based on the parsed intent
    and application context.
    """

    def translate(
        self,
        intent: QueryIntent,
        app_context: Optional[Dict[str, Any]] = None
    ) -> QueryTranslationResult:
        """
        Translate query intent into observability queries.

        Args:
            intent: Parsed query intent
            app_context: Optional application context with labels, metrics, etc.

        Returns:
            QueryTranslationResult with queries for each relevant backend
        """
        result = QueryTranslationResult(intent=intent)

        # Generate LogQL queries if logs are needed
        if intent.requires_logs:
            logql = self._generate_logql(intent, app_context)
            if logql:
                result.logql_queries.append(logql)

        # Generate TraceQL queries if traces are needed
        if intent.requires_traces:
            traceql = self._generate_traceql(intent, app_context)
            if traceql:
                result.traceql_queries.append(traceql)

        # Generate PromQL queries if metrics are needed
        if intent.requires_metrics:
            promql_queries = self._generate_promql(intent, app_context)
            result.promql_queries.extend(promql_queries)

        logger.info(
            f"Translated query: {len(result.logql_queries)} LogQL, "
            f"{len(result.traceql_queries)} TraceQL, "
            f"{len(result.promql_queries)} PromQL"
        )

        return result

    def _generate_logql(
        self,
        intent: QueryIntent,
        app_context: Optional[Dict[str, Any]] = None
    ) -> Optional[TranslatedQuery]:
        """Generate LogQL query from intent."""
        # Build label selectors
        selectors = []

        # Add application selector
        if intent.application_name:
            selectors.append(f'app="{intent.application_name}"')
        elif app_context and app_context.get("app_label"):
            selectors.append(f'app="{app_context["app_label"]}"')

        # Add service selector
        if intent.service_name:
            selectors.append(f'service="{intent.service_name}"')

        # Add environment selector
        if intent.environment:
            selectors.append(f'env="{intent.environment}"')

        # Default selector if none specified
        if not selectors:
            selectors.append('job="varlogs"')

        # Build the stream selector
        stream_selector = '{' + ', '.join(selectors) + '}'

        # Build line filters
        filters = []

        # Add log level filter
        if intent.log_level:
            level_pattern = intent.log_level.upper()
            filters.append(f'|~ "{level_pattern}"')

        # Add error pattern filter
        if intent.error_pattern:
            filters.append(f'|~ "{intent.error_pattern}"')

        # Add search terms as filters
        for term in intent.search_terms[:3]:  # Limit to 3 terms
            filters.append(f'|= "{term}"')

        # Add HTTP status code filter
        if intent.http_status_code:
            filters.append(f'|~ "status.*{intent.http_status_code}"')

        # Combine stream selector and filters
        query = stream_selector + ' '.join(filters)

        # Add aggregation if needed
        if intent.aggregate_function == 'count':
            # Use count_over_time for counting
            query = f'count_over_time({query}[{intent.time_range}])'

            if intent.group_by:
                # Group by labels
                by_clause = ', '.join(intent.group_by)
                query = f'sum by ({by_clause}) ({query})'

        return TranslatedQuery(
            query_language="logql",
            query=query,
            time_range=intent.time_range,
            start_time=intent.start_time,
            end_time=intent.end_time,
            limit=intent.limit
        )

    def _generate_traceql(
        self,
        intent: QueryIntent,
        app_context: Optional[Dict[str, Any]] = None
    ) -> Optional[TranslatedQuery]:
        """Generate TraceQL query from intent."""
        # Build TraceQL conditions
        conditions = []

        # Add service name filter
        if intent.service_name:
            conditions.append(f'resource.service.name="{intent.service_name}"')
        elif intent.application_name:
            conditions.append(f'resource.service.name="{intent.application_name}"')

        # Add HTTP status code filter
        if intent.http_status_code:
            conditions.append(f'http.status_code={intent.http_status_code}')

        # Add error filter
        if intent.intent_type == "errors" or intent.log_level == "error":
            # Look for error tags or status
            conditions.append('(error=true || status.code=2)')

        # Add search terms as span name or attribute filters
        for term in intent.search_terms[:2]:  # Limit to 2 terms
            conditions.append(f'(name=~".*{term}.*" || attributes["operation"]=~".*{term}.*")')

        # Build TraceQL query
        if conditions:
            query = '{' + ' && '.join(conditions) + '}'
        else:
            # Default query for all traces
            query = '{}'

        return TranslatedQuery(
            query_language="traceql",
            query=query,
            time_range=intent.time_range,
            start_time=intent.start_time,
            end_time=intent.end_time,
            limit=min(intent.limit, 20)  # Traces are heavy, limit to 20
        )

    def _generate_promql(
        self,
        intent: QueryIntent,
        app_context: Optional[Dict[str, Any]] = None
    ) -> List[TranslatedQuery]:
        """Generate PromQL queries from intent."""
        queries = []

        # Get metric prefix from app context
        metric_prefix = ""
        if app_context and app_context.get("metrics_prefix"):
            metric_prefix = app_context["metrics_prefix"]

        # Build label matchers
        label_matchers = []
        if intent.application_name:
            label_matchers.append(f'app="{intent.application_name}"')
        if intent.service_name:
            label_matchers.append(f'service="{intent.service_name}"')

        labels = '{' + ', '.join(label_matchers) + '}' if label_matchers else ''

        # Generate queries based on intent type
        if intent.intent_type == "errors":
            # Error rate query
            error_query = f'rate({metric_prefix}http_errors_total{labels}[{intent.time_range}])'
            queries.append(TranslatedQuery(
                query_language="promql",
                query=error_query,
                time_range=intent.time_range,
                limit=1
            ))

            # Total errors query
            total_errors = f'sum(increase({metric_prefix}http_errors_total{labels}[{intent.time_range}]))'
            queries.append(TranslatedQuery(
                query_language="promql",
                query=total_errors,
                time_range=intent.time_range,
                limit=1
            ))

        elif intent.intent_type == "performance":
            # Request duration P95
            p95_query = (
                f'histogram_quantile(0.95, '
                f'rate({metric_prefix}http_request_duration_seconds_bucket{labels}[{intent.time_range}]))'
            )
            queries.append(TranslatedQuery(
                query_language="promql",
                query=p95_query,
                time_range=intent.time_range,
                limit=1
            ))

            # Request duration P99
            p99_query = (
                f'histogram_quantile(0.99, '
                f'rate({metric_prefix}http_request_duration_seconds_bucket{labels}[{intent.time_range}]))'
            )
            queries.append(TranslatedQuery(
                query_language="promql",
                query=p99_query,
                time_range=intent.time_range,
                limit=1
            ))

        elif intent.intent_type == "health":
            # Uptime/availability query
            up_query = f'up{labels}'
            queries.append(TranslatedQuery(
                query_language="promql",
                query=up_query,
                time_range=intent.time_range,
                limit=1
            ))

            # Request success rate
            success_rate = (
                f'sum(rate({metric_prefix}http_requests_total{{status=~"2..",{labels.strip("{}")}}}[{intent.time_range}])) / '
                f'sum(rate({metric_prefix}http_requests_total{labels}[{intent.time_range}]))'
            )
            queries.append(TranslatedQuery(
                query_language="promql",
                query=success_rate,
                time_range=intent.time_range,
                limit=1
            ))

        elif intent.intent_type == "alerts":
            # Active firing alerts count
            count_query = f'count(ALERTS{{alertstate="firing",{labels.strip("{}")}}})'
            queries.append(TranslatedQuery(
                query_language="promql",
                query=count_query,
                time_range=intent.time_range,
                limit=1
            ))

            # List of active alerts
            list_query = f'ALERTS{{alertstate="firing",{labels.strip("{}")}}}'
            queries.append(TranslatedQuery(
                query_language="promql",
                query=list_query,
                time_range=intent.time_range,
                limit=10
            ))

        elif intent.intent_type == "metrics":
            # Generic metrics queries
            # Request rate
            request_rate = f'rate({metric_prefix}http_requests_total{labels}[{intent.time_range}])'
            queries.append(TranslatedQuery(
                query_language="promql",
                query=request_rate,
                time_range=intent.time_range,
                limit=1
            ))

            # CPU usage if available
            cpu_query = f'rate(process_cpu_seconds_total{labels}[{intent.time_range}])'
            queries.append(TranslatedQuery(
                query_language="promql",
                query=cpu_query,
                time_range=intent.time_range,
                limit=1
            ))

            # Memory usage
            memory_query = f'process_resident_memory_bytes{labels}'
            queries.append(TranslatedQuery(
                query_language="promql",
                query=memory_query,
                time_range=intent.time_range,
                limit=1
            ))

        return queries

    def build_context_from_profile(
        self,
        profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build query context from application profile.

        Args:
            profile_data: Application profile dictionary

        Returns:
            Context dictionary with labels, metrics, etc.
        """
        context = {}

        # Extract service mappings
        if "service_mappings" in profile_data:
            mappings = profile_data["service_mappings"]
            if mappings:
                # Use first service mapping as default
                first_service = list(mappings.values())[0]
                if "metrics_prefix" in first_service:
                    context["metrics_prefix"] = first_service["metrics_prefix"]
                if "log_label" in first_service:
                    # Parse log label like "service=app-api"
                    label_parts = first_service["log_label"].split("=")
                    if len(label_parts) == 2:
                        context["app_label"] = label_parts[1]

        # Extract default metrics
        if "default_metrics" in profile_data:
            context["default_metrics"] = profile_data["default_metrics"]

        # Extract architecture info
        if "architecture_type" in profile_data:
            context["architecture"] = profile_data["architecture_type"]

        return context


# Global translator instance
_query_translator: Optional[QueryTranslator] = None


def get_query_translator() -> QueryTranslator:
    """
    Get global query translator instance.

    Returns:
        Singleton QueryTranslator instance
    """
    global _query_translator
    if _query_translator is None:
        _query_translator = QueryTranslator()
    return _query_translator
