"""
Unit tests for TempoClient service.

Tests cover:
- Trace retrieval by ID
- Trace search with filters
- Tag name and value discovery
- Connection testing
- Jaeger and OTLP format parsing
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
import httpx

from app.services.tempo_client import TempoClient, Trace, Span, TraceSearchResult, get_tempo_client


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tempo_client():
    """Create a TempoClient instance for testing."""
    return TempoClient(url="http://test-tempo:3200", timeout=10)


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    return mock_response


@pytest.fixture
def sample_jaeger_trace():
    """Sample Jaeger-format trace response."""
    return {
        "batches": [
            {
                "process": {
                    "serviceName": "api-gateway"
                },
                "spans": [
                    {
                        "spanID": "span1",
                        "operationName": "GET /users",
                        "startTime": 1640000000000,  # microseconds
                        "duration": 150000,  # microseconds = 150ms
                        "tags": [
                            {"key": "http.method", "value": "GET"},
                            {"key": "http.status_code", "value": 200}
                        ],
                        "logs": [
                            {
                                "timestamp": 1640000050000,
                                "fields": [{"key": "event", "value": "cache_hit"}]
                            }
                        ],
                        "references": []  # Root span
                    },
                    {
                        "spanID": "span2",
                        "operationName": "query_database",
                        "startTime": 1640000010000,
                        "duration": 50000,  # 50ms
                        "tags": [
                            {"key": "db.type", "value": "postgresql"}
                        ],
                        "logs": [],
                        "references": [
                            {"refType": "CHILD_OF", "spanID": "span1"}
                        ]
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_otlp_trace():
    """Sample OTLP-format trace response."""
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "web-service"}}
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "spanId": "abc123",
                                "name": "handle_request",
                                "startTimeUnixNano": "1640000000000000000",
                                "endTimeUnixNano": "1640000200000000000",
                                "attributes": [
                                    {"key": "http.method", "value": {"stringValue": "POST"}},
                                    {"key": "http.status_code", "value": {"intValue": 201}}
                                ],
                                "parentSpanId": ""  # Root span
                            },
                            {
                                "spanId": "def456",
                                "name": "authenticate",
                                "startTimeUnixNano": "1640000010000000000",
                                "endTimeUnixNano": "1640000050000000000",
                                "attributes": [
                                    {"key": "user.id", "value": {"stringValue": "user123"}}
                                ],
                                "parentSpanId": "abc123"
                            }
                        ]
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_search_response():
    """Sample trace search response."""
    return {
        "traces": [
            {
                "traceID": "trace-001",
                "rootServiceName": "frontend",
                "rootTraceName": "page_load",
                "startTimeUnixNano": 1640000000000000000,
                "durationMs": 250,
                "spanSets": [
                    {"matched": 3}
                ]
            },
            {
                "traceID": "trace-002",
                "rootServiceName": "api-gateway",
                "rootTraceName": "GET /api/data",
                "startTimeUnixNano": 1640001000000000000,
                "durationMs": 180,
                "spanSets": []
            }
        ]
    }


@pytest.fixture
def sample_tag_names_response():
    """Sample tag names response."""
    return {
        "tagNames": [
            "http.method",
            "http.status_code",
            "service.name",
            "db.type",
            "error"
        ]
    }


@pytest.fixture
def sample_tag_values_response():
    """Sample tag values response."""
    return {
        "tagValues": ["GET", "POST", "PUT", "DELETE", "PATCH"]
    }


# ============================================================================
# Test TempoClient Initialization
# ============================================================================

def test_tempo_client_init_default():
    """Test TempoClient initialization with default values."""
    with patch.dict("os.environ", {"TEMPO_URL": "http://env-tempo:3200"}):
        client = TempoClient()
        assert client.url == "http://env-tempo:3200"
        assert client.base_url == "http://env-tempo:3200"
        assert client.timeout == 30


def test_tempo_client_init_custom():
    """Test TempoClient initialization with custom values."""
    client = TempoClient(url="http://custom-tempo:4200", timeout=60)
    assert client.url == "http://custom-tempo:4200"
    assert client.base_url == "http://custom-tempo:4200"
    assert client.timeout == 60


def test_tempo_client_init_trailing_slash():
    """Test TempoClient strips trailing slash from URL."""
    client = TempoClient(url="http://tempo:3200/")
    assert client.base_url == "http://tempo:3200"


# ============================================================================
# Test get_trace() - Jaeger Format
# ============================================================================

@pytest.mark.asyncio
async def test_get_trace_jaeger_format(tempo_client, sample_jaeger_trace, mock_httpx_response):
    """Test successful trace retrieval in Jaeger format."""
    mock_httpx_response.json = Mock(return_value=sample_jaeger_trace)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        trace = await tempo_client.get_trace("trace123")

        # Verify request
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "http://test-tempo:3200/api/traces/trace123"

        # Verify trace parsing
        assert isinstance(trace, Trace)
        assert trace.trace_id == "trace123"
        assert trace.root_service_name == "api-gateway"
        assert trace.root_trace_name == "GET /users"
        assert len(trace.spans) == 2
        assert trace.total_spans == 2
        assert trace.duration_ms > 0

        # Verify span details
        assert trace.spans[0].span_id == "span1"
        assert trace.spans[0].operation_name == "GET /users"
        assert trace.spans[0].service_name == "api-gateway"
        assert trace.spans[0].tags["http.method"] == "GET"
        assert len(trace.spans[0].logs) == 1


@pytest.mark.asyncio
async def test_get_trace_otlp_format(tempo_client, sample_otlp_trace, mock_httpx_response):
    """Test successful trace retrieval in OTLP format."""
    mock_httpx_response.json = Mock(return_value=sample_otlp_trace)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        trace = await tempo_client.get_trace("trace456")

        # Verify trace parsing
        assert isinstance(trace, Trace)
        assert trace.trace_id == "trace456"
        assert trace.root_service_name == "web-service"
        assert trace.root_trace_name == "handle_request"
        assert len(trace.spans) == 2

        # Verify OTLP-specific parsing
        assert trace.spans[0].span_id == "abc123"
        assert trace.spans[0].operation_name == "handle_request"
        assert trace.spans[0].tags["http.method"] == "POST"
        assert trace.spans[0].tags["http.status_code"] == 201


@pytest.mark.asyncio
async def test_get_trace_not_found(tempo_client):
    """Test trace not found returns None."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
        "404 Not Found",
        request=Mock(),
        response=mock_response
    ))

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        trace = await tempo_client.get_trace("nonexistent")

        assert trace is None


@pytest.mark.asyncio
async def test_get_trace_empty_spans(tempo_client, mock_httpx_response):
    """Test trace with no spans returns None."""
    empty_trace = {"batches": []}
    mock_httpx_response.json = Mock(return_value=empty_trace)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        trace = await tempo_client.get_trace("empty-trace")

        assert trace is None


# ============================================================================
# Test search_traces() - Trace Search
# ============================================================================

@pytest.mark.asyncio
async def test_search_traces_success(tempo_client, sample_search_response, mock_httpx_response):
    """Test successful trace search."""
    mock_httpx_response.json = Mock(return_value=sample_search_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        results = await tempo_client.search_traces(
            tags={"http.status_code": "500"},
            limit=10
        )

        # Verify request
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "http://test-tempo:3200/api/search"
        assert call_args[1]["params"]["limit"] == 10
        assert 'http.status_code="500"' in call_args[1]["params"]["q"]

        # Verify results
        assert len(results) == 2
        assert all(isinstance(r, TraceSearchResult) for r in results)
        assert results[0].trace_id == "trace-001"
        assert results[0].root_service_name == "frontend"
        assert results[0].duration_ms == 250


@pytest.mark.asyncio
async def test_search_traces_with_duration_filters(tempo_client, sample_search_response, mock_httpx_response):
    """Test trace search with duration filters."""
    mock_httpx_response.json = Mock(return_value=sample_search_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        await tempo_client.search_traces(
            min_duration="100ms",
            max_duration="1s",
            limit=20
        )

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["minDuration"] == "100ms"
        assert call_args[1]["params"]["maxDuration"] == "1s"


@pytest.mark.asyncio
async def test_search_traces_with_time_range(tempo_client, sample_search_response, mock_httpx_response):
    """Test trace search with time range."""
    mock_httpx_response.json = Mock(return_value=sample_search_response)

    start = datetime.now() - timedelta(hours=1)
    end = datetime.now()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        await tempo_client.search_traces(start=start, end=end)

        call_args = mock_client.get.call_args
        assert "start" in call_args[1]["params"]
        assert "end" in call_args[1]["params"]
        assert call_args[1]["params"]["start"] == int(start.timestamp())
        assert call_args[1]["params"]["end"] == int(end.timestamp())


@pytest.mark.asyncio
async def test_search_traces_with_service_name(tempo_client, sample_search_response, mock_httpx_response):
    """Test trace search with service name filter."""
    mock_httpx_response.json = Mock(return_value=sample_search_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        await tempo_client.search_traces(service_name="api-gateway")

        call_args = mock_client.get.call_args
        assert 'resource.service.name="api-gateway"' in call_args[1]["params"]["q"]


@pytest.mark.asyncio
async def test_search_traces_with_span_name(tempo_client, sample_search_response, mock_httpx_response):
    """Test trace search with span name filter."""
    mock_httpx_response.json = Mock(return_value=sample_search_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        await tempo_client.search_traces(span_name="GET /users")

        call_args = mock_client.get.call_args
        assert 'name="GET /users"' in call_args[1]["params"]["q"]


@pytest.mark.asyncio
async def test_search_traces_empty_results(tempo_client, mock_httpx_response):
    """Test trace search with no results."""
    empty_response = {"traces": []}
    mock_httpx_response.json = Mock(return_value=empty_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        results = await tempo_client.search_traces()

        assert results == []


# ============================================================================
# Test get_tag_names() - Tag Discovery
# ============================================================================

@pytest.mark.asyncio
async def test_get_tag_names_success(tempo_client, sample_tag_names_response, mock_httpx_response):
    """Test successful tag name discovery."""
    mock_httpx_response.json = Mock(return_value=sample_tag_names_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        tags = await tempo_client.get_tag_names()

        # Verify request
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "http://test-tempo:3200/api/search/tags"

        # Verify response
        assert tags == ["http.method", "http.status_code", "service.name", "db.type", "error"]


@pytest.mark.asyncio
async def test_get_tag_names_with_time_range(tempo_client, sample_tag_names_response, mock_httpx_response):
    """Test tag name discovery with time range."""
    mock_httpx_response.json = Mock(return_value=sample_tag_names_response)

    start = datetime.now() - timedelta(hours=24)
    end = datetime.now()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        await tempo_client.get_tag_names(start=start, end=end)

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["start"] == int(start.timestamp())
        assert call_args[1]["params"]["end"] == int(end.timestamp())


# ============================================================================
# Test get_tag_values() - Tag Value Queries
# ============================================================================

@pytest.mark.asyncio
async def test_get_tag_values_success(tempo_client, sample_tag_values_response, mock_httpx_response):
    """Test successful tag value query."""
    mock_httpx_response.json = Mock(return_value=sample_tag_values_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        values = await tempo_client.get_tag_values("http.method")

        # Verify request
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "http://test-tempo:3200/api/search/tag/http.method/values"

        # Verify response
        assert values == ["GET", "POST", "PUT", "DELETE", "PATCH"]


@pytest.mark.asyncio
async def test_get_tag_values_with_time_range(tempo_client, sample_tag_values_response, mock_httpx_response):
    """Test tag value query with time range."""
    mock_httpx_response.json = Mock(return_value=sample_tag_values_response)

    start = datetime.now() - timedelta(hours=12)
    end = datetime.now()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        await tempo_client.get_tag_values("service.name", start=start, end=end)

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["start"] == int(start.timestamp())
        assert call_args[1]["params"]["end"] == int(end.timestamp())


# ============================================================================
# Test test_connection() - Connection Testing
# ============================================================================

@pytest.mark.asyncio
async def test_connection_success(tempo_client):
    """Test successful connection to Tempo."""
    mock_response = Mock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await tempo_client.test_connection()

        assert result is True
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "http://test-tempo:3200/ready"


@pytest.mark.asyncio
async def test_connection_failure(tempo_client):
    """Test connection failure to Tempo."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client_class.return_value = mock_client

        result = await tempo_client.test_connection()

        assert result is False


@pytest.mark.asyncio
async def test_connection_not_ready(tempo_client):
    """Test Tempo not ready returns False."""
    mock_response = Mock()
    mock_response.status_code = 503

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await tempo_client.test_connection()

        assert result is False


# ============================================================================
# Test Error Handling
# ============================================================================

@pytest.mark.asyncio
async def test_get_trace_http_error(tempo_client):
    """Test get_trace with HTTP error."""
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
        "500 Server Error",
        request=Mock(),
        response=mock_response
    ))

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception):
            await tempo_client.get_trace("trace123")


@pytest.mark.asyncio
async def test_search_traces_http_error(tempo_client):
    """Test search_traces with HTTP error."""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
        "400 Bad Request",
        request=Mock(),
        response=mock_response
    ))

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception):
            await tempo_client.search_traces()


@pytest.mark.asyncio
async def test_get_tag_names_http_error(tempo_client):
    """Test get_tag_names with HTTP error."""
    mock_response = Mock()
    mock_response.status_code = 503
    mock_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
        "503 Service Unavailable",
        request=Mock(),
        response=mock_response
    ))

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception):
            await tempo_client.get_tag_names()


# ============================================================================
# Test Global Client Instance
# ============================================================================

def test_get_tempo_client_singleton():
    """Test get_tempo_client returns singleton instance."""
    client1 = get_tempo_client()
    client2 = get_tempo_client()

    assert client1 is client2


def test_get_tempo_client_default_config():
    """Test get_tempo_client creates client with default config."""
    # Reset global client
    import app.services.tempo_client as tempo_module
    tempo_module._tempo_client = None

    with patch.dict("os.environ", {"TEMPO_URL": "http://default-tempo:3200"}):
        client = get_tempo_client()
        assert client.url == "http://default-tempo:3200"
        assert client.timeout == 30
