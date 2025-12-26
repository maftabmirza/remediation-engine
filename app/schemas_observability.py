"""
Pydantic Schemas for Observability Query API

Request and response models for AI-powered observability queries.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class ObservabilityQueryRequest(BaseModel):
    """Schema for natural language observability query"""
    query: str = Field(..., min_length=1, description="Natural language query")
    application_id: Optional[UUID] = Field(None, description="Optional application ID for context")
    time_range: Optional[str] = Field(None, description="Optional time range override (e.g., '1h', '24h')")
    session_id: Optional[UUID] = Field(None, description="Optional inquiry session ID for grouping queries")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query": "Show me error logs for my-app in the last hour",
            "application_id": "550e8400-e29b-41d4-a716-446655440000",
            "time_range": "1h"
        }
    })


class QueryIntentResponse(BaseModel):
    """Schema for query intent classification"""
    intent_type: str
    confidence: float
    requires_logs: bool
    requires_traces: bool
    requires_metrics: bool
    application_name: Optional[str]
    service_name: Optional[str]
    time_range: str
    log_level: Optional[str]

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "intent_type": "errors",
            "confidence": 0.85,
            "requires_logs": True,
            "requires_traces": False,
            "requires_metrics": True,
            "application_name": "my-app",
            "service_name": None,
            "time_range": "1h",
            "log_level": "error"
        }
    })


class LogEntryResponse(BaseModel):
    """Schema for log entry in response"""
    timestamp: str
    line: str
    labels: Dict[str, str]

    model_config = ConfigDict(from_attributes=True)


class LogsResultResponse(BaseModel):
    """Schema for logs query results"""
    entries: List[LogEntryResponse]
    total_count: int
    query: str
    time_range: str

    model_config = ConfigDict(from_attributes=True)


class TraceResponse(BaseModel):
    """Schema for trace search result"""
    trace_id: str
    root_service_name: str
    root_trace_name: str
    start_time_unix_nano: int
    duration_ms: int

    model_config = ConfigDict(from_attributes=True)


class TracesResultResponse(BaseModel):
    """Schema for traces query results"""
    traces: List[TraceResponse]
    total_count: int
    query: str
    time_range: str

    model_config = ConfigDict(from_attributes=True)


class MetricValueResponse(BaseModel):
    """Schema for metric data point"""
    timestamp: float
    value: float


class MetricsResultResponse(BaseModel):
    """Schema for metrics query results"""
    metric_name: str
    query: str
    value: Optional[float]
    values: List[MetricValueResponse]
    time_range: str

    model_config = ConfigDict(from_attributes=True)


class ObservabilityQueryResponse(BaseModel):
    """Schema for complete observability query response"""
    # Original query
    original_query: str
    intent: QueryIntentResponse

    # Results from each backend
    logs_results: List[LogsResultResponse]
    traces_results: List[TracesResultResponse]
    metrics_results: List[MetricsResultResponse]

    # Summary
    total_logs: int
    total_traces: int
    total_metrics: int

    # Execution metadata
    execution_time_ms: float
    backends_queried: List[str]
    errors: List[str]

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "original_query": "Show me errors in the last hour",
            "intent": {
                "intent_type": "errors",
                "confidence": 0.9,
                "requires_logs": True,
                "requires_traces": False,
                "requires_metrics": True,
                "application_name": "my-app",
                "service_name": None,
                "time_range": "1h",
                "log_level": "error"
            },
            "logs_results": [],
            "traces_results": [],
            "metrics_results": [],
            "total_logs": 45,
            "total_traces": 0,
            "total_metrics": 2,
            "execution_time_ms": 234.5,
            "backends_queried": ["loki", "prometheus"],
            "errors": []
        }
    })


class TranslatedQueryResponse(BaseModel):
    """Schema for showing translated queries (debug endpoint)"""
    query_language: str
    query: str
    time_range: str

    model_config = ConfigDict(from_attributes=True)


class QueryTranslationResponse(BaseModel):
    """Schema for query translation debug response"""
    original_query: str
    intent: QueryIntentResponse
    logql_queries: List[TranslatedQueryResponse]
    traceql_queries: List[TranslatedQueryResponse]
    promql_queries: List[TranslatedQueryResponse]

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "original_query": "Show me errors",
            "intent": {
                "intent_type": "errors",
                "confidence": 0.9,
                "requires_logs": True,
                "requires_traces": False,
                "requires_metrics": True,
                "application_name": None,
                "service_name": None,
                "time_range": "1h",
                "log_level": "error"
            },
            "logql_queries": [
                {
                    "query_language": "logql",
                    "query": '{job="varlogs"} |~ "ERROR"',
                    "time_range": "1h"
                }
            ],
            "traceql_queries": [],
            "promql_queries": [
                {
                    "query_language": "promql",
                    "query": "rate(http_errors_total[1h])",
                    "time_range": "1h"
                }
            ]
        }
    })
