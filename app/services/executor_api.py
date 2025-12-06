"""
API Executor - HTTP/REST API Execution

Provides HTTP/REST API execution capabilities for automation workflows.
Supports common API patterns like Ansible AWX, Jenkins, and generic REST APIs.

Features:
- Multiple authentication methods (API Key, Bearer, Basic, OAuth)
- Request templating with Jinja2
- Response validation and extraction
- Retry logic for transient failures
- SSL verification control
"""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlencode
import httpx
from jinja2 import Template, TemplateError

from app.services.executor_base import BaseExecutor, ExecutionResult, ServerInfo, ErrorType


class APIExecutor(BaseExecutor):
    """
    HTTP/REST API executor for making API calls as part of remediation workflows.

    Implements the BaseExecutor interface but adapted for HTTP APIs instead of
    command execution. The 'execute' method makes HTTP requests instead of
    running commands.
    """

    def __init__(
        self,
        hostname: str,
        port: int = 443,
        username: str = "",
        base_url: Optional[str] = None,
        auth_type: str = "none",  # none, api_key, bearer, basic, oauth, custom
        auth_header: Optional[str] = None,
        auth_token: Optional[str] = None,
        verify_ssl: bool = True,
        timeout: int = 30,
        default_headers: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize API executor.

        Args:
            hostname: API server hostname
            port: API server port (default 443 for HTTPS)
            username: Username for basic auth (optional)
            base_url: Base URL for API (e.g., https://api.example.com/v1)
            auth_type: Authentication type (none, api_key, bearer, basic, oauth, custom)
            auth_header: Header name for authentication (e.g., "X-API-Key", "Authorization")
            auth_token: API token/key/password for authentication
            verify_ssl: Whether to verify SSL certificates
            timeout: Default timeout for requests in seconds
            default_headers: Default headers to include in all requests
            metadata: Provider-specific metadata
        """
        super().__init__(hostname, port, username, timeout)

        # API Configuration
        self.base_url = base_url or f"https://{hostname}:{port}"
        self.auth_type = auth_type
        self.auth_header = auth_header
        self.auth_token = auth_token
        self.verify_ssl = verify_ssl
        self.default_headers = default_headers or {}
        self.metadata = metadata or {}

        # HTTP client (created on connect)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def protocol(self) -> str:
        """Return the protocol name."""
        return "api"

    @property
    def supports_elevation(self) -> bool:
        """APIs don't support privilege elevation like sudo."""
        return False

    async def connect(self) -> bool:
        """
        Create HTTP client session.

        Returns:
            bool: True if client created successfully.
        """
        try:
            # Create async HTTP client with configuration
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                verify=self.verify_ssl,
                follow_redirects=True,
                headers=self._build_default_headers()
            )

            self._connected = True
            return True

        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to create API client: {str(e)}")

    async def disconnect(self) -> None:
        """Close HTTP client session."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False

    async def test_connection(self) -> bool:
        """
        Test API connectivity with a simple request.

        Attempts a GET request to the base URL or a health endpoint.

        Returns:
            bool: True if API is reachable.
        """
        try:
            if not self._client:
                await self.connect()

            # Try to make a simple GET request
            # Most APIs support GET to base URL or /health, /status, /ping
            test_paths = ["/health", "/status", "/ping", "/api/health", "/"]

            for path in test_paths:
                try:
                    response = await self._client.get(path, timeout=5)
                    if response.status_code < 500:  # Any non-server-error is considered success
                        return True
                except httpx.HTTPStatusError:
                    continue
                except httpx.RequestError:
                    continue

            return False

        except Exception:
            return False

    async def get_server_info(self) -> ServerInfo:
        """
        Get API server information.

        For APIs, this is limited to basic connectivity info.

        Returns:
            ServerInfo with basic API details.
        """
        return ServerInfo(
            hostname=self.hostname,
            os_type="api",
            os_version=None,
            kernel_version=None,
            architecture=None,
            uptime_seconds=None
        )

    async def execute(
        self,
        command: str,  # For APIs, this is JSON config: {"method": "POST", "endpoint": "/api/jobs", "body": {...}}
        timeout: Optional[int] = None,
        with_elevation: bool = False,  # Not applicable for APIs
        env: Optional[Dict[str, str]] = None,  # Used as template variables
        working_directory: Optional[str] = None  # Not applicable for APIs
    ) -> ExecutionResult:
        """
        Execute an API request.

        The 'command' parameter should be a JSON string with the request configuration:
        {
            "method": "POST",
            "endpoint": "/api/v2/job_templates/123/launch/",
            "headers": {"Content-Type": "application/json"},
            "query_params": {"verbose": "true"},
            "body": "{\"extra_vars\": {\"target\": \"{{ instance }}\"}}",
            "body_type": "json",
            "expected_status_codes": [200, 201, 202],
            "extract": {"job_id": "$.id"}
        }

        Args:
            command: JSON string with API request configuration
            timeout: Request timeout in seconds
            env: Template variables for Jinja2 rendering
            with_elevation: Not applicable for APIs (ignored)
            working_directory: Not applicable for APIs (ignored)

        Returns:
            ExecutionResult with API response details.
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Ensure client is connected
            if not self._client:
                await self.connect()

            # Parse command as JSON config
            try:
                config = json.loads(command)
            except json.JSONDecodeError as e:
                return self._error_result(
                    command=command,
                    error_type=ErrorType.COMMAND,
                    error_message=f"Invalid API command JSON: {str(e)}",
                    start_time=start_time
                )

            # Extract request parameters
            method = config.get("method", "GET").upper()
            endpoint = config.get("endpoint", "/")
            headers = config.get("headers", {})
            query_params = config.get("query_params", {})
            body = config.get("body")
            body_type = config.get("body_type", "json")
            expected_status_codes = config.get("expected_status_codes", [200, 201, 202, 204])
            extract_patterns = config.get("extract", {})
            follow_redirects = config.get("follow_redirects", True)

            # Render templates if env variables provided
            if env:
                endpoint = self._render_template(endpoint, env)
                if body:
                    body = self._render_template(body, env)
                # Render query params
                query_params = {k: self._render_template(str(v), env) for k, v in query_params.items()}

            # Build full URL
            url = self._build_url(endpoint, query_params)

            # Merge headers
            request_headers = {**self.default_headers, **headers}

            # Prepare request body
            request_body = self._prepare_body(body, body_type)

            # Make HTTP request
            effective_timeout = timeout or self.timeout

            response = await self._client.request(
                method=method,
                url=url,
                headers=request_headers,
                content=request_body if isinstance(request_body, (str, bytes)) else None,
                json=request_body if isinstance(request_body, dict) and body_type == "json" else None,
                data=request_body if isinstance(request_body, dict) and body_type == "form" else None,
                timeout=effective_timeout,
                follow_redirects=follow_redirects
            )

            # Calculate duration
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Extract values from response
            extracted_values = {}
            if extract_patterns and response.text:
                extracted_values = self._extract_values(response.text, extract_patterns)

            # Check if status code is expected
            success = response.status_code in expected_status_codes

            # Build execution result
            return ExecutionResult(
                success=success,
                exit_code=response.status_code,  # Use HTTP status code as "exit code"
                stdout=response.text,  # Response body as stdout
                stderr="" if success else f"HTTP {response.status_code}: {response.reason_phrase}",
                duration_ms=duration_ms,
                command=command,
                server_hostname=self.hostname,
                executed_at=start_time,
                error_type=ErrorType.COMMAND if not success else None,
                error_message=None if success else f"Unexpected status code: {response.status_code}",
                retryable=response.status_code in [408, 429, 500, 502, 503, 504],
                output_lines=[response.text] if response.text else []
            )

        except httpx.TimeoutException as e:
            return self._error_result(
                command=command,
                error_type=ErrorType.TIMEOUT,
                error_message=f"Request timeout: {str(e)}",
                start_time=start_time,
                retryable=True
            )

        except httpx.ConnectError as e:
            return self._error_result(
                command=command,
                error_type=ErrorType.CONNECTION,
                error_message=f"Connection error: {str(e)}",
                start_time=start_time,
                retryable=True
            )

        except httpx.HTTPStatusError as e:
            return self._error_result(
                command=command,
                error_type=ErrorType.AUTH if e.response.status_code in [401, 403] else ErrorType.COMMAND,
                error_message=f"HTTP error: {e.response.status_code} {e.response.reason_phrase}",
                start_time=start_time,
                retryable=e.response.status_code in [408, 429, 500, 502, 503, 504]
            )

        except Exception as e:
            return self._error_result(
                command=command,
                error_type=ErrorType.UNKNOWN,
                error_message=f"Unexpected error: {str(e)}",
                start_time=start_time,
                retryable=False
            )

    def _build_default_headers(self) -> Dict[str, str]:
        """Build default headers including authentication."""
        headers = {
            "User-Agent": "AIOps-Remediation-Engine/1.0",
            **self.default_headers
        }

        # Add authentication header
        if self.auth_type == "api_key" and self.auth_header and self.auth_token:
            headers[self.auth_header] = self.auth_token

        elif self.auth_type == "bearer" and self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        elif self.auth_type == "basic" and self.username and self.auth_token:
            import base64
            credentials = base64.b64encode(f"{self.username}:{self.auth_token}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"

        elif self.auth_type == "custom" and self.auth_header and self.auth_token:
            headers[self.auth_header] = self.auth_token

        return headers

    def _build_url(self, endpoint: str, query_params: Optional[Dict[str, str]] = None) -> str:
        """Build full URL from endpoint and query parameters."""
        # If endpoint is already a full URL, use it as-is
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            url = endpoint
        else:
            # Combine base URL with endpoint
            url = urljoin(self.base_url, endpoint)

        # Add query parameters
        if query_params:
            query_string = urlencode(query_params)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query_string}"

        return url

    def _prepare_body(self, body: Optional[str], body_type: str) -> Optional[Any]:
        """Prepare request body based on body_type."""
        if not body:
            return None

        if body_type == "json":
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                # If it's not valid JSON, return as string
                return body

        elif body_type == "form":
            # Parse form data (key=value&key2=value2)
            try:
                return dict(item.split("=", 1) for item in body.split("&"))
            except ValueError:
                return body

        elif body_type in ["raw", "template"]:
            return body

        return body

    def _render_template(self, template_str: str, variables: Dict[str, str]) -> str:
        """Render Jinja2 template with variables."""
        try:
            template = Template(template_str)
            return template.render(**variables)
        except TemplateError as e:
            # If template rendering fails, return original string
            return template_str

    def _extract_values(self, response_body: str, patterns: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract values from response body using JSONPath or regex.

        Args:
            response_body: API response body
            patterns: Dict of {key: pattern} where pattern is JSONPath ($.path) or regex

        Returns:
            Dict of extracted values
        """
        extracted = {}

        # Try to parse response as JSON
        try:
            response_json = json.loads(response_body)
            is_json = True
        except json.JSONDecodeError:
            is_json = False

        for key, pattern in patterns.items():
            # JSONPath extraction (simple implementation)
            if pattern.startswith("$.") and is_json:
                value = self._extract_jsonpath(response_json, pattern)
                if value is not None:
                    extracted[key] = value

            # Regex extraction
            else:
                match = re.search(pattern, response_body)
                if match:
                    extracted[key] = match.group(1) if match.groups() else match.group(0)

        return extracted

    def _extract_jsonpath(self, data: Any, path: str) -> Any:
        """
        Simple JSONPath extraction (supports basic paths like $.key.subkey).

        For more complex JSONPath, consider using jsonpath-ng library.
        """
        # Remove leading $. and split by dots
        keys = path[2:].split(".")

        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                index = int(key)
                current = current[index] if index < len(current) else None
            else:
                return None

            if current is None:
                return None

        return current

    def _error_result(
        self,
        command: str,
        error_type: ErrorType,
        error_message: str,
        start_time: datetime,
        retryable: bool = False
    ) -> ExecutionResult:
        """Create an error ExecutionResult."""
        end_time = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return ExecutionResult(
            success=False,
            exit_code=-1,
            stdout="",
            stderr=error_message,
            duration_ms=duration_ms,
            command=command,
            server_hostname=self.hostname,
            executed_at=start_time,
            error_type=error_type,
            error_message=error_message,
            retryable=retryable
        )

    # File operations not applicable for APIs
    async def upload_file(self, local_path: str, remote_path: str) -> bool:
        """File upload not supported for API executor."""
        raise NotImplementedError("File upload is not applicable for API executor")

    async def download_file(self, remote_path: str, local_path: str) -> bool:
        """File download not supported for API executor."""
        raise NotImplementedError("File download is not applicable for API executor")
