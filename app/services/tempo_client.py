"""
Tempo Client Service

Provides methods to query Grafana Tempo distributed tracing system.
Supports trace queries, search, and metadata retrieval.
"""

import httpx
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class Span(BaseModel):
    """Single span in a trace"""
    trace_id: str
    span_id: str
    operation_name: str
    start_time_unix_nano: int
    duration_nanos: int
    tags: Dict[str, Any] = {}
    logs: List[Dict[str, Any]] = []
    references: List[Dict[str, str]] = []
    service_name: Optional[str] = None
    warnings: List[str] = []


class Trace(BaseModel):
    """Complete distributed trace"""
    trace_id: str
    root_service_name: Optional[str] = None
    root_trace_name: Optional[str] = None
    start_time_unix_nano: int
    duration_ms: int
    spans: List[Span]
    total_spans: int = 0


class TraceSearchResult(BaseModel):
    """Search result for traces"""
    trace_id: str
    root_service_name: str
    root_trace_name: str
    start_time_unix_nano: int
    duration_ms: int
    span_sets: List[Dict[str, Any]] = []


class TempoClient:
    """
    Client for querying Grafana Tempo.

    Supports:
    - Trace lookup by ID
    - Trace search by tags and metadata
    - Service discovery
    - Tag name and value queries
    """

    def __init__(self, url: Optional[str] = None, timeout: int = 30):
        """
        Initialize Tempo client.

        Args:
            url: Tempo base URL (default: from TEMPO_URL env var)
            timeout: Request timeout in seconds
        """
        self.url = url or os.getenv("TEMPO_URL", "http://tempo:3200")
        self.timeout = timeout
        self.base_url = self.url.rstrip("/")

    async def get_trace(self, trace_id: str) -> Optional[Trace]:
        """
        Retrieve a trace by its ID.

        Args:
            trace_id: Trace ID (hex string, 16 or 32 characters)

        Returns:
            Trace object or None if not found

        Example:
            trace = await client.get_trace("1234567890abcdef")
        """
        url = f"{self.base_url}/api/traces/{trace_id}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()

                # Parse trace data
                if "batches" in data and len(data["batches"]) > 0:
                    return self._parse_trace(trace_id, data)
                elif "resourceSpans" in data and len(data["resourceSpans"]) > 0:
                    return self._parse_otlp_trace(trace_id, data)
                else:
                    logger.warning(f"Trace {trace_id} found but has no spans")
                    return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"Trace {trace_id} not found")
                return None
            logger.error(f"Tempo get_trace failed: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Tempo get_trace failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Tempo get_trace error: {str(e)}")
            raise

    async def search_traces(
        self,
        tags: Optional[Dict[str, str]] = None,
        min_duration: Optional[str] = None,
        max_duration: Optional[str] = None,
        limit: int = 20,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        service_name: Optional[str] = None,
        span_name: Optional[str] = None
    ) -> List[TraceSearchResult]:
        """
        Search for traces by tags and metadata.

        Args:
            tags: Dictionary of tag key-value pairs to search
            min_duration: Minimum trace duration (e.g., "100ms", "1s")
            max_duration: Maximum trace duration
            limit: Maximum number of results
            start: Start time for search window
            end: End time for search window
            service_name: Filter by service name
            span_name: Filter by span/operation name

        Returns:
            List of trace search results

        Example:
            results = await client.search_traces(
                tags={"http.status_code": "500"},
                min_duration="1s",
                service_name="api-gateway"
            )
        """
        url = f"{self.base_url}/api/search"

        # Build query parameters
        params: Dict[str, Any] = {"limit": limit}

        if tags:
            # TraceQL query format: {tag1="value1" && tag2="value2"}
            tag_conditions = [f'{k}="{v}"' for k, v in tags.items()]
            params["q"] = "{" + " && ".join(tag_conditions) + "}"

        if min_duration:
            params["minDuration"] = min_duration

        if max_duration:
            params["maxDuration"] = max_duration

        if start:
            params["start"] = int(start.timestamp())

        if end:
            params["end"] = int(end.timestamp())

        # Add service/span filters to TraceQL query
        if service_name or span_name:
            query_parts = []
            if service_name:
                query_parts.append(f'resource.service.name="{service_name}"')
            if span_name:
                query_parts.append(f'name="{span_name}"')

            if "q" in params:
                # Merge with existing query
                existing = params["q"].strip("{}")
                if existing:
                    query_parts.append(existing)

            params["q"] = "{" + " && ".join(query_parts) + "}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                # Parse search results
                results = []
                for trace_data in data.get("traces", []):
                    result = TraceSearchResult(
                        trace_id=trace_data.get("traceID", ""),
                        root_service_name=trace_data.get("rootServiceName", ""),
                        root_trace_name=trace_data.get("rootTraceName", ""),
                        start_time_unix_nano=trace_data.get("startTimeUnixNano", 0),
                        duration_ms=trace_data.get("durationMs", 0),
                        span_sets=trace_data.get("spanSets", [])
                    )
                    results.append(result)

                logger.info(f"Found {len(results)} traces matching search criteria")
                return results

        except httpx.HTTPStatusError as e:
            logger.error(f"Tempo search_traces failed: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Tempo search_traces failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Tempo search_traces error: {str(e)}")
            raise

    async def get_tag_names(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[str]:
        """
        Get all tag names available in Tempo.

        Args:
            start: Start time for tag discovery
            end: End time for tag discovery

        Returns:
            List of tag names

        Example:
            tags = await client.get_tag_names()
            # ["http.method", "http.status_code", "service.name", ...]
        """
        url = f"{self.base_url}/api/search/tags"

        params = {}
        if start:
            params["start"] = int(start.timestamp())
        if end:
            params["end"] = int(end.timestamp())

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                tags = data.get("tagNames", [])

                logger.info(f"Found {len(tags)} tag names")
                return tags

        except httpx.HTTPStatusError as e:
            logger.error(f"Tempo get_tag_names failed: {e.response.status_code}")
            raise Exception(f"Tempo get_tag_names failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Tempo get_tag_names error: {str(e)}")
            raise

    async def get_tag_values(
        self,
        tag_name: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[str]:
        """
        Get all values for a specific tag.

        Args:
            tag_name: Tag name to query
            start: Start time for value discovery
            end: End time for value discovery

        Returns:
            List of tag values

        Example:
            values = await client.get_tag_values("http.method")
            # ["GET", "POST", "PUT", "DELETE"]
        """
        url = f"{self.base_url}/api/search/tag/{tag_name}/values"

        params = {}
        if start:
            params["start"] = int(start.timestamp())
        if end:
            params["end"] = int(end.timestamp())

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                values = data.get("tagValues", [])

                logger.info(f"Found {len(values)} values for tag '{tag_name}'")
                return values

        except httpx.HTTPStatusError as e:
            logger.error(f"Tempo get_tag_values failed: {e.response.status_code}")
            raise Exception(f"Tempo get_tag_values failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Tempo get_tag_values error: {str(e)}")
            raise

    async def test_connection(self) -> bool:
        """
        Test connection to Tempo.

        Returns:
            True if connection successful, False otherwise

        Example:
            if await client.test_connection():
                print("Tempo is ready")
        """
        url = f"{self.base_url}/ready"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    logger.info("Tempo connection successful")
                    return True
                else:
                    logger.warning(f"Tempo not ready: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Tempo connection failed: {str(e)}")
            return False

    def _parse_trace(self, trace_id: str, data: Dict[str, Any]) -> Trace:
        """Parse Jaeger-format trace data."""
        spans = []
        start_time = None
        end_time = None
        root_service = None
        root_operation = None

        for batch in data.get("batches", []):
            process = batch.get("process", {})
            service_name = process.get("serviceName", "unknown")

            for span_data in batch.get("spans", []):
                span_id = span_data.get("spanID", "")
                operation_name = span_data.get("operationName", "")
                start_time_us = span_data.get("startTime", 0)
                duration_us = span_data.get("duration", 0)

                # Convert microseconds to nanoseconds
                start_time_nano = start_time_us * 1000
                duration_nano = duration_us * 1000

                # Extract tags
                tags = {}
                for tag in span_data.get("tags", []):
                    tags[tag.get("key", "")] = tag.get("value", "")

                # Extract logs
                logs = []
                for log in span_data.get("logs", []):
                    logs.append({
                        "timestamp": log.get("timestamp", 0),
                        "fields": log.get("fields", [])
                    })

                # Extract references
                references = span_data.get("references", [])

                span = Span(
                    trace_id=trace_id,
                    span_id=span_id,
                    operation_name=operation_name,
                    start_time_unix_nano=start_time_nano,
                    duration_nanos=duration_nano,
                    tags=tags,
                    logs=logs,
                    references=references,
                    service_name=service_name
                )
                spans.append(span)

                # Track trace bounds
                if start_time is None or start_time_nano < start_time:
                    start_time = start_time_nano

                span_end = start_time_nano + duration_nano
                if end_time is None or span_end > end_time:
                    end_time = span_end

                # Identify root span (no parent references)
                if not references or all(ref.get("refType") != "CHILD_OF" for ref in references):
                    root_service = service_name
                    root_operation = operation_name

        duration_ms = int((end_time - start_time) / 1_000_000) if start_time and end_time else 0

        return Trace(
            trace_id=trace_id,
            root_service_name=root_service,
            root_trace_name=root_operation,
            start_time_unix_nano=start_time or 0,
            duration_ms=duration_ms,
            spans=spans,
            total_spans=len(spans)
        )

    def _parse_otlp_trace(self, trace_id: str, data: Dict[str, Any]) -> Trace:
        """Parse OTLP (OpenTelemetry Protocol) format trace data."""
        spans = []
        start_time = None
        end_time = None
        root_service = None
        root_operation = None

        for resource_span in data.get("resourceSpans", []):
            resource = resource_span.get("resource", {})
            attributes = {
                attr.get("key"): attr.get("value", {}).get("stringValue", "")
                for attr in resource.get("attributes", [])
            }
            service_name = attributes.get("service.name", "unknown")

            for scope_span in resource_span.get("scopeSpans", []):
                for span_data in scope_span.get("spans", []):
                    span_id = span_data.get("spanId", "")
                    operation_name = span_data.get("name", "")
                    start_time_nano = int(span_data.get("startTimeUnixNano", 0))
                    end_time_nano = int(span_data.get("endTimeUnixNano", 0))
                    duration_nano = end_time_nano - start_time_nano

                    # Extract attributes as tags
                    tags = {}
                    for attr in span_data.get("attributes", []):
                        key = attr.get("key", "")
                        value_obj = attr.get("value", {})
                        # Handle different value types
                        value = (
                            value_obj.get("stringValue") or
                            value_obj.get("intValue") or
                            value_obj.get("boolValue") or
                            value_obj.get("doubleValue") or
                            ""
                        )
                        tags[key] = value

                    span = Span(
                        trace_id=trace_id,
                        span_id=span_id,
                        operation_name=operation_name,
                        start_time_unix_nano=start_time_nano,
                        duration_nanos=duration_nano,
                        tags=tags,
                        service_name=service_name
                    )
                    spans.append(span)

                    # Track trace bounds
                    if start_time is None or start_time_nano < start_time:
                        start_time = start_time_nano

                    if end_time is None or end_time_nano > end_time:
                        end_time = end_time_nano

                    # Identify root span (no parent)
                    if not span_data.get("parentSpanId"):
                        root_service = service_name
                        root_operation = operation_name

        duration_ms = int((end_time - start_time) / 1_000_000) if start_time and end_time else 0

        return Trace(
            trace_id=trace_id,
            root_service_name=root_service,
            root_trace_name=root_operation,
            start_time_unix_nano=start_time or 0,
            duration_ms=duration_ms,
            spans=spans,
            total_spans=len(spans)
        )


# Global client instance
_tempo_client: Optional[TempoClient] = None


def get_tempo_client() -> TempoClient:
    """
    Get global Tempo client instance.

    Returns:
        Singleton TempoClient instance

    Example:
        client = get_tempo_client()
        trace = await client.get_trace("abc123")
    """
    global _tempo_client
    if _tempo_client is None:
        _tempo_client = TempoClient()
    return _tempo_client
