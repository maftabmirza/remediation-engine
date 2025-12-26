"""
Loki Client Service

Provides methods to query Loki log aggregation system.
Supports LogQL queries for log retrieval and analysis.
"""

import httpx
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class LogEntry(BaseModel):
    """Single log entry from Loki"""
    timestamp: str
    line: str
    labels: Dict[str, str] = {}


class LogStream(BaseModel):
    """Log stream with labels and entries"""
    stream: Dict[str, str]
    values: List[List[str]]  # [[timestamp, line], ...]


class LokiQueryResponse(BaseModel):
    """Loki query response"""
    status: str
    data: Dict[str, Any]


class LokiClient:
    """
    Client for querying Grafana Loki.

    Supports:
    - Instant log queries
    - Range log queries
    - Label discovery
    - Label value queries
    """

    def __init__(self, url: Optional[str] = None, timeout: int = 30):
        """
        Initialize Loki client.

        Args:
            url: Loki base URL (default: from LOKI_URL env var)
            timeout: Request timeout in seconds
        """
        self.url = url or os.getenv("LOKI_URL", "http://loki:3100")
        self.timeout = timeout
        self.base_url = self.url.rstrip("/")

    async def query(
        self,
        logql: str,
        limit: int = 1000,
        time: Optional[datetime] = None,
        direction: str = "backward"
    ) -> List[LogEntry]:
        """
        Execute instant LogQL query.

        Args:
            logql: LogQL query string (e.g., '{job="varlogs"}')
            limit: Maximum number of entries to return
            time: Query time (default: now)
            direction: "forward" or "backward"

        Returns:
            List of log entries

        Example:
            entries = await client.query('{app="my-app"} |= "error"', limit=100)
        """
        params = {
            "query": logql,
            "limit": limit,
            "direction": direction
        }

        if time:
            params["time"] = int(time.timestamp() * 1e9)  # Nanoseconds

        url = f"{self.base_url}/loki/api/v1/query"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                if data.get("status") != "success":
                    raise Exception(f"Loki query failed: {data}")

                # Parse response
                entries = []
                result = data.get("data", {}).get("result", [])

                for stream in result:
                    labels = stream.get("stream", {})
                    values = stream.get("values", [])

                    for value in values:
                        timestamp_ns, line = value
                        entries.append(LogEntry(
                            timestamp=timestamp_ns,
                            line=line,
                            labels=labels
                        ))

                return entries

        except httpx.HTTPStatusError as e:
            logger.error(f"Loki HTTP error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Loki query failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Loki query error: {str(e)}")
            raise

    async def query_range(
        self,
        logql: str,
        start: datetime,
        end: datetime,
        limit: int = 1000,
        step: Optional[str] = None,
        direction: str = "backward"
    ) -> List[LogEntry]:
        """
        Execute range LogQL query.

        Args:
            logql: LogQL query string
            start: Start time
            end: End time
            limit: Maximum number of entries
            step: Query resolution step (e.g., "5m")
            direction: "forward" or "backward"

        Returns:
            List of log entries

        Example:
            start = datetime.now() - timedelta(hours=1)
            end = datetime.now()
            entries = await client.query_range(
                '{app="my-app"} |= "error"',
                start=start,
                end=end,
                limit=500
            )
        """
        params = {
            "query": logql,
            "start": int(start.timestamp() * 1e9),  # Nanoseconds
            "end": int(end.timestamp() * 1e9),
            "limit": limit,
            "direction": direction
        }

        if step:
            params["step"] = step

        url = f"{self.base_url}/loki/api/v1/query_range"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                if data.get("status") != "success":
                    raise Exception(f"Loki query_range failed: {data}")

                # Parse response
                entries = []
                result = data.get("data", {}).get("result", [])

                for stream in result:
                    labels = stream.get("stream", {})
                    values = stream.get("values", [])

                    for value in values:
                        timestamp_ns, line = value
                        entries.append(LogEntry(
                            timestamp=timestamp_ns,
                            line=line,
                            labels=labels
                        ))

                return entries

        except httpx.HTTPStatusError as e:
            logger.error(f"Loki HTTP error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Loki query_range failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Loki query_range error: {str(e)}")
            raise

    async def get_labels(self, start: Optional[datetime] = None, end: Optional[datetime] = None) -> List[str]:
        """
        Get all label names.

        Args:
            start: Start time (optional)
            end: End time (optional)

        Returns:
            List of label names

        Example:
            labels = await client.get_labels()
            # ['app', 'job', 'namespace', 'pod']
        """
        params = {}

        if start:
            params["start"] = int(start.timestamp() * 1e9)
        if end:
            params["end"] = int(end.timestamp() * 1e9)

        url = f"{self.base_url}/loki/api/v1/labels"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                if data.get("status") != "success":
                    raise Exception(f"Loki get_labels failed: {data}")

                return data.get("data", [])

        except httpx.HTTPStatusError as e:
            logger.error(f"Loki HTTP error: {e.response.status_code}")
            raise Exception(f"Loki get_labels failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Loki get_labels error: {str(e)}")
            raise

    async def get_label_values(
        self,
        label: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[str]:
        """
        Get all values for a specific label.

        Args:
            label: Label name
            start: Start time (optional)
            end: End time (optional)

        Returns:
            List of label values

        Example:
            apps = await client.get_label_values("app")
            # ['app-1', 'app-2', 'app-3']
        """
        params = {}

        if start:
            params["start"] = int(start.timestamp() * 1e9)
        if end:
            params["end"] = int(end.timestamp() * 1e9)

        url = f"{self.base_url}/loki/api/v1/label/{label}/values"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                if data.get("status") != "success":
                    raise Exception(f"Loki get_label_values failed: {data}")

                return data.get("data", [])

        except httpx.HTTPStatusError as e:
            logger.error(f"Loki HTTP error: {e.response.status_code}")
            raise Exception(f"Loki get_label_values failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Loki get_label_values error: {str(e)}")
            raise

    async def test_connection(self) -> bool:
        """
        Test connection to Loki.

        Returns:
            True if connected, False otherwise
        """
        url = f"{self.base_url}/ready"

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Loki connection test failed: {str(e)}")
            return False

    async def count_logs(
        self,
        logql: str,
        start: datetime,
        end: datetime,
        step: str = "1m"
    ) -> int:
        """
        Count log entries matching LogQL query over time range.

        Args:
            logql: LogQL query
            start: Start time
            end: End time
            step: Aggregation step

        Returns:
            Total count of log entries

        Example:
            count = await client.count_logs(
                '{app="my-app"} |= "error"',
                start=datetime.now() - timedelta(hours=24),
                end=datetime.now()
            )
        """
        # Use count_over_time aggregation
        count_query = f'count_over_time({logql}[{step}])'

        entries = await self.query_range(
            logql=count_query,
            start=start,
            end=end,
            step=step,
            limit=10000
        )

        # Sum up all counts from the time series
        total = 0
        for entry in entries:
            try:
                # Parse the count value from the log line
                count_value = float(entry.line)
                total += count_value
            except (ValueError, TypeError):
                continue

        return int(total)


# Global client instance
_loki_client: Optional[LokiClient] = None


def get_loki_client() -> LokiClient:
    """
    Get global Loki client instance.

    Returns:
        LokiClient instance
    """
    global _loki_client
    if _loki_client is None:
        _loki_client = LokiClient()
    return _loki_client
