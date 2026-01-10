"""
Query Intent Parser

Analyzes natural language queries to determine:
- What type of observability data is needed (logs, traces, metrics)
- Time range for the query
- Application/service context
- Specific conditions or filters
- Aggregation requirements
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel
import re
import logging

logger = logging.getLogger(__name__)


class QueryIntent(BaseModel):
    """Parsed intent from a natural language query"""

    # Primary intent classification
    intent_type: str  # "logs", "traces", "metrics", "health", "errors", "performance"

    # Data source requirements
    requires_logs: bool = False
    requires_traces: bool = False
    requires_metrics: bool = False

    # Context filters
    application_name: Optional[str] = None
    service_name: Optional[str] = None
    component_name: Optional[str] = None
    environment: Optional[str] = None

    # Time range
    time_range: str = "1h"  # Default to last hour
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Conditions and filters
    log_level: Optional[str] = None  # error, warn, info, debug
    http_status_code: Optional[str] = None
    error_pattern: Optional[str] = None

    # Aggregation
    aggregate_function: Optional[str] = None  # count, avg, max, min, sum, rate
    group_by: List[str] = []

    # Query specifics
    limit: int = 100
    search_terms: List[str] = []

    # Original query
    original_query: str
    confidence: float = 0.0  # 0.0 to 1.0


class QueryIntentParser:
    """
    Parses natural language queries to extract intent and parameters.

    Uses pattern matching and keyword analysis to classify queries and
    extract relevant parameters for observability data retrieval.
    """

    # Intent classification patterns
    LOGS_PATTERNS = [
        r'\b(logs?|logging|log entries)\b',
        r'\b(show|display|get|find|search).*(logs?)\b',
        r'\berror logs?\b',
        r'\bwarning logs?\b',
    ]

    TRACES_PATTERNS = [
        r'\b(traces?|tracing|spans?)\b',
        r'\b(distributed tracing|request trace)\b',
        r'\bshow.*trace\b',
        r'\btrace.*requests?\b',
    ]

    METRICS_PATTERNS = [
        r'\b(metrics?|measurements?)\b',
        r'\b(cpu|memory|disk|network).*usage\b',
        r'\b(requests? per second|rps|throughput)\b',
        r'\b(latency|response time|duration)\b',
        r'\b(error rate|success rate)\b',
    ]

    ERROR_PATTERNS = [
        r'\b(errors?|failures?|failed)\b',
        r'\b(exceptions?|crashes?)\b',
        r'\b(5\d\d|500|503|504)\b',  # HTTP error codes
        r'\b(error rate|failure rate)\b',
    ]

    PERFORMANCE_PATTERNS = [
        r'\b(slow|slowness|latency|performance)\b',
        r'\b(response time|duration|speed)\b',
        r'\b(p95|p99|percentile)\b',
    ]

    HEALTH_PATTERNS = [
        r'\b(health|healthy|status|availability)\b',
        r'\b(up|down|uptime|downtime)\b',
        r'\bis.*running\b',
    ]

    # Time range patterns
    TIME_PATTERNS = {
        r'\b(last|past) (\d+) (second|minute|hour|day|week)s?\b': lambda m: f"{m.group(2)}{m.group(3)[0]}",
        r'\btoday\b': '1d',
        r'\byesterday\b': '1d',
        r'\bthis week\b': '7d',
        r'\bthis month\b': '30d',
    }

    # Log level patterns
    LOG_LEVEL_PATTERNS = {
        r'\b(error|errors)\b': 'error',
        r'\b(warning|warnings|warn)\b': 'warn',
        r'\b(info|information)\b': 'info',
        r'\b(debug|debugging)\b': 'debug',
    }

    # Application/service patterns
    APP_PATTERNS = [
        r'\bfor ([\w-]+) (app|application|service)\b',
        r'\bin ([\w-]+) (app|application|service)\b',
        r'\b(app|application|service)[:\s]+([\w-]+)\b',
    ]

    # HTTP status code patterns
    HTTP_STATUS_PATTERNS = {
        r'\b(2\d\d|200|201|204)\b': 'success',
        r'\b(4\d\d|400|401|403|404)\b': 'client_error',
        r'\b(5\d\d|500|502|503|504)\b': 'server_error',
    }

    def parse(self, query: str) -> QueryIntent:
        """
        Parse a natural language query into structured intent.

        Args:
            query: Natural language query string

        Returns:
            QueryIntent with parsed parameters and classification
        """
        query_lower = query.lower()

        # Initialize intent
        intent = QueryIntent(
            original_query=query,
            intent_type="logs",  # Default
            confidence=0.5
        )

        # Classify primary intent
        intent_scores = {
            "errors": self._score_patterns(query_lower, self.ERROR_PATTERNS),
            "performance": self._score_patterns(query_lower, self.PERFORMANCE_PATTERNS),
            "health": self._score_patterns(query_lower, self.HEALTH_PATTERNS),
            "logs": self._score_patterns(query_lower, self.LOGS_PATTERNS),
            "traces": self._score_patterns(query_lower, self.TRACES_PATTERNS),
            "metrics": self._score_patterns(query_lower, self.METRICS_PATTERNS),
        }

        # Select highest scoring intent
        intent.intent_type = max(intent_scores, key=intent_scores.get)
        intent.confidence = intent_scores[intent.intent_type]

        # Determine required data sources
        intent.requires_logs = (
            intent_scores["logs"] > 0 or
            intent.intent_type in ["errors", "logs"]
        )
        intent.requires_traces = (
            intent_scores["traces"] > 0 or
            intent.intent_type == "traces"
        )
        intent.requires_metrics = (
            intent_scores["metrics"] > 0 or
            intent.intent_type in ["performance", "health", "metrics"]
        )

        # Extract time range
        intent.time_range = self._extract_time_range(query_lower)

        # Extract application/service
        intent.application_name = self._extract_application(query)

        # Extract log level
        intent.log_level = self._extract_log_level(query_lower)

        # Extract HTTP status
        intent.http_status_code = self._extract_http_status(query_lower)

        # Extract search terms (remove common words)
        intent.search_terms = self._extract_search_terms(query_lower)

        # Extract aggregation
        intent.aggregate_function, intent.group_by = self._extract_aggregation(query_lower)

        # Extract limit
        intent.limit = self._extract_limit(query_lower)

        logger.info(f"Parsed query intent: {intent.intent_type} (confidence: {intent.confidence:.2f})")

        return intent

    def _score_patterns(self, query: str, patterns: List[str]) -> float:
        """Score how well query matches a set of patterns."""
        matches = 0
        for pattern in patterns:
            if re.search(pattern, query, re.IGNORECASE):
                matches += 1

        return min(matches / max(len(patterns), 1), 1.0)

    def _extract_time_range(self, query: str) -> str:
        """Extract time range from query."""
        for pattern, handler in self.TIME_PATTERNS.items():
            match = re.search(pattern, query)
            if match:
                if callable(handler):
                    return handler(match)
                return handler

        return "1h"  # Default

    def _extract_application(self, query: str) -> Optional[str]:
        """Extract application/service name from query."""
        for pattern in self.APP_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # Return the captured application name (first group)
                for group in match.groups():
                    if group not in ['app', 'application', 'service', 'for', 'in']:
                        return group

        return None

    def _extract_log_level(self, query: str) -> Optional[str]:
        """Extract log level from query."""
        for pattern, level in self.LOG_LEVEL_PATTERNS.items():
            if re.search(pattern, query):
                return level

        return None

    def _extract_http_status(self, query: str) -> Optional[str]:
        """Extract HTTP status code pattern from query."""
        for pattern, status_type in self.HTTP_STATUS_PATTERNS.items():
            match = re.search(pattern, query)
            if match:
                return match.group(1)

        return None

    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract meaningful search terms from query."""
        # Remove common words
        common_words = {
            'show', 'me', 'get', 'find', 'search', 'display', 'list', 'what',
            'are', 'is', 'the', 'for', 'in', 'on', 'at', 'from', 'to', 'with',
            'and', 'or', 'not', 'last', 'past', 'recent', 'all', 'any',
            'logs', 'log', 'traces', 'trace', 'metrics', 'metric'
        }

        # Extract quoted strings first
        quoted = re.findall(r'"([^"]+)"', query)

        # Split on whitespace and filter
        words = query.split()
        meaningful = [
            w for w in words
            if len(w) > 2 and w not in common_words and not w.isdigit()
        ]

        return quoted + meaningful[:5]  # Limit to 5 terms

    def _extract_aggregation(self, query: str) -> Tuple[Optional[str], List[str]]:
        """Extract aggregation function and group by fields."""
        agg_function = None

        # Check for aggregation functions
        agg_patterns = {
            r'\bcount\b': 'count',
            r'\baverage\b|\bavg\b': 'avg',
            r'\bmaximum\b|\bmax\b': 'max',
            r'\bminimum\b|\bmin\b': 'min',
            r'\bsum\b|\btotal\b': 'sum',
            r'\brate\b': 'rate',
        }

        for pattern, func in agg_patterns.items():
            if re.search(pattern, query):
                agg_function = func
                break

        # Check for group by
        group_by = []
        group_by_match = re.search(r'\bby ([\w,\s]+)', query)
        if group_by_match:
            group_by = [g.strip() for g in group_by_match.group(1).split(',')]

        return agg_function, group_by

    def _extract_limit(self, query: str) -> int:
        """Extract result limit from query."""
        # Look for "top N" or "limit N"
        limit_match = re.search(r'\b(top|limit|first|last)\s+(\d+)\b', query)
        if limit_match:
            return int(limit_match.group(2))

        return 100  # Default


# Global parser instance
_intent_parser: Optional[QueryIntentParser] = None


def get_intent_parser() -> QueryIntentParser:
    """
    Get global query intent parser instance.

    Returns:
        Singleton QueryIntentParser instance
    """
    global _intent_parser
    if _intent_parser is None:
        _intent_parser = QueryIntentParser()
    return _intent_parser
