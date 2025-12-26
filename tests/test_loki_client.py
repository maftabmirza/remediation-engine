"""
Unit tests for LokiClient service.

Tests cover:
- Instant log queries
- Range log queries
- Label discovery
- Label value queries
- Connection testing
- Log counting
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
import httpx

from app.services.loki_client import LokiClient, LogEntry, get_loki_client


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def loki_client():
    """Create a LokiClient instance for testing."""
    return LokiClient(url="http://test-loki:3100", timeout=10)


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    return mock_response


@pytest.fixture
def sample_query_response():
    """Sample Loki instant query response."""
    return {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {
                        "app": "my-app",
                        "level": "error",
                        "pod": "my-app-123"
                    },
                    "values": [
                        ["1640000000000000000", "Error: Connection timeout"],
                        ["1640000001000000000", "Error: Database unavailable"]
                    ]
                },
                {
                    "stream": {
                        "app": "my-app",
                        "level": "error",
                        "pod": "my-app-456"
                    },
                    "values": [
                        ["1640000002000000000", "Error: Invalid request"]
                    ]
                }
            ]
        }
    }


@pytest.fixture
def sample_range_query_response():
    """Sample Loki range query response."""
    return {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {
                        "job": "varlogs",
                        "filename": "/var/log/app.log"
                    },
                    "values": [
                        ["1640000000000000000", "INFO: Application started"],
                        ["1640000010000000000", "WARN: High memory usage"],
                        ["1640000020000000000", "ERROR: Failed to connect"]
                    ]
                }
            ]
        }
    }


@pytest.fixture
def sample_labels_response():
    """Sample Loki labels response."""
    return {
        "status": "success",
        "data": ["app", "environment", "job", "level", "namespace", "pod"]
    }


@pytest.fixture
def sample_label_values_response():
    """Sample Loki label values response."""
    return {
        "status": "success",
        "data": ["app-1", "app-2", "app-3", "my-app"]
    }


# ============================================================================
# Test LokiClient Initialization
# ============================================================================

def test_loki_client_init_default():
    """Test LokiClient initialization with default values."""
    with patch.dict("os.environ", {"LOKI_URL": "http://env-loki:3100"}):
        client = LokiClient()
        assert client.url == "http://env-loki:3100"
        assert client.base_url == "http://env-loki:3100"
        assert client.timeout == 30


def test_loki_client_init_custom():
    """Test LokiClient initialization with custom values."""
    client = LokiClient(url="http://custom-loki:3200", timeout=60)
    assert client.url == "http://custom-loki:3200"
    assert client.base_url == "http://custom-loki:3200"
    assert client.timeout == 60


def test_loki_client_init_trailing_slash():
    """Test LokiClient strips trailing slash from URL."""
    client = LokiClient(url="http://loki:3100/")
    assert client.base_url == "http://loki:3100"


# ============================================================================
# Test query() - Instant Queries
# ============================================================================

@pytest.mark.asyncio
async def test_query_success(loki_client, sample_query_response, mock_httpx_response):
    """Test successful instant LogQL query."""
    mock_httpx_response.json = Mock(return_value=sample_query_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        entries = await loki_client.query('{app="my-app"} |= "error"', limit=100)

        # Verify request
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "http://test-loki:3100/loki/api/v1/query"
        assert call_args[1]["params"]["query"] == '{app="my-app"} |= "error"'
        assert call_args[1]["params"]["limit"] == 100
        assert call_args[1]["params"]["direction"] == "backward"

        # Verify response parsing
        assert len(entries) == 3
        assert all(isinstance(entry, LogEntry) for entry in entries)
        assert entries[0].timestamp == "1640000000000000000"
        assert entries[0].line == "Error: Connection timeout"
        assert entries[0].labels == {"app": "my-app", "level": "error", "pod": "my-app-123"}


@pytest.mark.asyncio
async def test_query_with_time(loki_client, sample_query_response, mock_httpx_response):
    """Test instant query with specific timestamp."""
    mock_httpx_response.json = Mock(return_value=sample_query_response)
    query_time = datetime(2021, 12, 20, 10, 0, 0)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        await loki_client.query('{job="varlogs"}', time=query_time)

        call_args = mock_client.get.call_args
        assert "time" in call_args[1]["params"]
        assert call_args[1]["params"]["time"] == int(query_time.timestamp() * 1e9)


@pytest.mark.asyncio
async def test_query_forward_direction(loki_client, sample_query_response, mock_httpx_response):
    """Test instant query with forward direction."""
    mock_httpx_response.json = Mock(return_value=sample_query_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        await loki_client.query('{app="test"}', direction="forward")

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["direction"] == "forward"


@pytest.mark.asyncio
async def test_query_empty_results(loki_client, mock_httpx_response):
    """Test query with no results."""
    empty_response = {
        "status": "success",
        "data": {"resultType": "streams", "result": []}
    }
    mock_httpx_response.json = Mock(return_value=empty_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        entries = await loki_client.query('{app="nonexistent"}')

        assert entries == []


# ============================================================================
# Test query_range() - Range Queries
# ============================================================================

@pytest.mark.asyncio
async def test_query_range_success(loki_client, sample_range_query_response, mock_httpx_response):
    """Test successful range LogQL query."""
    mock_httpx_response.json = Mock(return_value=sample_range_query_response)

    start = datetime.now() - timedelta(hours=1)
    end = datetime.now()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        entries = await loki_client.query_range(
            '{job="varlogs"}',
            start=start,
            end=end,
            limit=500
        )

        # Verify request
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "http://test-loki:3100/loki/api/v1/query_range"
        assert call_args[1]["params"]["query"] == '{job="varlogs"}'
        assert call_args[1]["params"]["start"] == int(start.timestamp() * 1e9)
        assert call_args[1]["params"]["end"] == int(end.timestamp() * 1e9)
        assert call_args[1]["params"]["limit"] == 500

        # Verify response
        assert len(entries) == 3
        assert entries[0].line == "INFO: Application started"
        assert entries[1].line == "WARN: High memory usage"
        assert entries[2].line == "ERROR: Failed to connect"


@pytest.mark.asyncio
async def test_query_range_with_step(loki_client, sample_range_query_response, mock_httpx_response):
    """Test range query with step parameter."""
    mock_httpx_response.json = Mock(return_value=sample_range_query_response)

    start = datetime.now() - timedelta(hours=1)
    end = datetime.now()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        await loki_client.query_range(
            '{app="test"}',
            start=start,
            end=end,
            step="5m"
        )

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["step"] == "5m"


# ============================================================================
# Test get_labels() - Label Discovery
# ============================================================================

@pytest.mark.asyncio
async def test_get_labels_success(loki_client, sample_labels_response, mock_httpx_response):
    """Test successful label discovery."""
    mock_httpx_response.json = Mock(return_value=sample_labels_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        labels = await loki_client.get_labels()

        # Verify request
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "http://test-loki:3100/loki/api/v1/labels"

        # Verify response
        assert labels == ["app", "environment", "job", "level", "namespace", "pod"]


@pytest.mark.asyncio
async def test_get_labels_with_time_range(loki_client, sample_labels_response, mock_httpx_response):
    """Test label discovery with time range."""
    mock_httpx_response.json = Mock(return_value=sample_labels_response)

    start = datetime.now() - timedelta(hours=1)
    end = datetime.now()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        await loki_client.get_labels(start=start, end=end)

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["start"] == int(start.timestamp() * 1e9)
        assert call_args[1]["params"]["end"] == int(end.timestamp() * 1e9)


# ============================================================================
# Test get_label_values() - Label Value Queries
# ============================================================================

@pytest.mark.asyncio
async def test_get_label_values_success(loki_client, sample_label_values_response, mock_httpx_response):
    """Test successful label value query."""
    mock_httpx_response.json = Mock(return_value=sample_label_values_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        values = await loki_client.get_label_values("app")

        # Verify request
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "http://test-loki:3100/loki/api/v1/label/app/values"

        # Verify response
        assert values == ["app-1", "app-2", "app-3", "my-app"]


@pytest.mark.asyncio
async def test_get_label_values_with_time_range(loki_client, sample_label_values_response, mock_httpx_response):
    """Test label value query with time range."""
    mock_httpx_response.json = Mock(return_value=sample_label_values_response)

    start = datetime.now() - timedelta(hours=24)
    end = datetime.now()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        await loki_client.get_label_values("namespace", start=start, end=end)

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["start"] == int(start.timestamp() * 1e9)
        assert call_args[1]["params"]["end"] == int(end.timestamp() * 1e9)


# ============================================================================
# Test test_connection() - Connection Testing
# ============================================================================

@pytest.mark.asyncio
async def test_connection_success(loki_client):
    """Test successful connection to Loki."""
    mock_response = Mock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await loki_client.test_connection()

        assert result is True
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "http://test-loki:3100/ready"


@pytest.mark.asyncio
async def test_connection_failure(loki_client):
    """Test connection failure to Loki."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client_class.return_value = mock_client

        result = await loki_client.test_connection()

        assert result is False


# ============================================================================
# Test count_logs() - Log Counting
# ============================================================================

@pytest.mark.asyncio
async def test_count_logs_success(loki_client, mock_httpx_response):
    """Test successful log counting."""
    count_response = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "stream": {},
                    "values": [
                        ["1640000000000000000", "10"],
                        ["1640000060000000000", "15"],
                        ["1640000120000000000", "8"]
                    ]
                }
            ]
        }
    }
    mock_httpx_response.json = Mock(return_value=count_response)

    start = datetime.now() - timedelta(hours=1)
    end = datetime.now()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        count = await loki_client.count_logs(
            '{app="my-app"} |= "error"',
            start=start,
            end=end,
            step="1m"
        )

        # Verify count_over_time query was used
        call_args = mock_client.get.call_args
        assert "count_over_time" in call_args[1]["params"]["query"]

        # Verify total count (10 + 15 + 8 = 33)
        assert count == 33


@pytest.mark.asyncio
async def test_count_logs_invalid_values(loki_client, mock_httpx_response):
    """Test log counting with invalid values (should skip them)."""
    count_response = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "stream": {},
                    "values": [
                        ["1640000000000000000", "5"],
                        ["1640000060000000000", "invalid"],
                        ["1640000120000000000", "3"]
                    ]
                }
            ]
        }
    }
    mock_httpx_response.json = Mock(return_value=count_response)

    start = datetime.now() - timedelta(hours=1)
    end = datetime.now()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        count = await loki_client.count_logs(
            '{app="test"}',
            start=start,
            end=end
        )

        # Should skip invalid value and return 5 + 3 = 8
        assert count == 8


# ============================================================================
# Test Error Handling
# ============================================================================

@pytest.mark.asyncio
async def test_query_http_error(loki_client):
    """Test query with HTTP error."""
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
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="Loki query failed: 500"):
            await loki_client.query('{app="test"}')


@pytest.mark.asyncio
async def test_query_failed_status(loki_client, mock_httpx_response):
    """Test query with failed status in response."""
    failed_response = {
        "status": "error",
        "error": "parse error at line 1, col 1: syntax error"
    }
    mock_httpx_response.json = Mock(return_value=failed_response)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_httpx_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="Loki query failed"):
            await loki_client.query('{invalid query}')


@pytest.mark.asyncio
async def test_query_range_http_error(loki_client):
    """Test query_range with HTTP error."""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
        "400 Bad Request",
        request=Mock(),
        response=mock_response
    ))

    start = datetime.now() - timedelta(hours=1)
    end = datetime.now()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="Loki query_range failed: 400"):
            await loki_client.query_range('{app="test"}', start=start, end=end)


@pytest.mark.asyncio
async def test_get_labels_http_error(loki_client):
    """Test get_labels with HTTP error."""
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
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="Loki get_labels failed: 503"):
            await loki_client.get_labels()


@pytest.mark.asyncio
async def test_get_label_values_http_error(loki_client):
    """Test get_label_values with HTTP error."""
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
        mock_client.__aexit__.return_value = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        with pytest.raises(Exception, match="Loki get_label_values failed: 404"):
            await loki_client.get_label_values("app")


# ============================================================================
# Test Global Client Instance
# ============================================================================

def test_get_loki_client_singleton():
    """Test get_loki_client returns singleton instance."""
    client1 = get_loki_client()
    client2 = get_loki_client()

    assert client1 is client2


def test_get_loki_client_default_config():
    """Test get_loki_client creates client with default config."""
    # Reset global client
    import app.services.loki_client as loki_module
    loki_module._loki_client = None

    with patch.dict("os.environ", {"LOKI_URL": "http://default-loki:3100"}):
        client = get_loki_client()
        assert client.url == "http://default-loki:3100"
        assert client.timeout == 30
