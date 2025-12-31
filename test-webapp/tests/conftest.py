"""
Pytest configuration and custom reporter plugin

This module provides:
1. Custom pytest plugin to report results to the test-webapp API
2. Shared fixtures for all tests
3. Test configuration and setup
"""
import pytest
import httpx
import json
import os
from typing import List, Dict, Any
from datetime import datetime


# Custom Pytest Reporter Plugin
class TestWebAppReporter:
    """
    Custom pytest plugin that reports test results to the test-webapp API
    """

    def __init__(self, config):
        self.config = config
        self.run_id = config.getoption("--run-id", None)
        self.webhook_url = config.getoption("--webhook-url", "http://localhost:8001/webhook/pytest-results")
        self.results: List[Dict[str, Any]] = []
        self.start_time = None
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def pytest_sessionstart(self, session):
        """Called when test session starts"""
        self.start_time = datetime.utcnow()
        print(f"\n[TestWebAppReporter] Starting test session, run_id: {self.run_id}")

    def pytest_runtest_logreport(self, report):
        """Called after each test phase (setup, call, teardown)"""
        # We only care about the 'call' phase (the actual test)
        if report.when != "call":
            return

        # Extract test ID from nodeid (e.g., tests/e2e/linux/test_linux.py::test_L01 -> L01)
        test_id = self._extract_test_id(report.nodeid)

        # Determine status
        if report.passed:
            status = "passed"
            self.passed += 1
        elif report.failed:
            status = "failed"
            self.failed += 1
        elif report.skipped:
            status = "skipped"
            self.skipped += 1
        else:
            status = "error"

        # Get error info
        error_message = None
        stack_trace = None
        if report.failed:
            error_message = str(report.longrepr) if hasattr(report, 'longrepr') else None
            if hasattr(report.longrepr, 'reprtraceback'):
                stack_trace = str(report.longrepr.reprtraceback)

        # Capture stdout/stderr
        stdout = report.capstdout if hasattr(report, 'capstdout') else None
        stderr = report.capstderr if hasattr(report, 'capstderr') else None

        result = {
            "test_id": test_id,
            "status": status,
            "duration": report.duration,
            "error_message": error_message,
            "stack_trace": stack_trace,
            "stdout": stdout,
            "stderr": stderr
        }

        self.results.append(result)
        print(f"[TestWebAppReporter] Test {test_id}: {status} ({report.duration:.2f}s)")

    def pytest_sessionfinish(self, session, exitstatus):
        """Called when test session ends"""
        if not self.run_id:
            print("[TestWebAppReporter] No run_id provided, skipping webhook")
            return

        # Calculate total duration
        duration = (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0

        # Prepare payload
        payload = {
            "run_id": int(self.run_id),
            "status": "completed" if exitstatus == 0 else "failed",
            "total_tests": len(self.results),
            "passed_tests": self.passed,
            "failed_tests": self.failed,
            "skipped_tests": self.skipped,
            "duration": duration,
            "results": self.results,
            "metadata": {
                "exit_status": exitstatus,
                "pytest_version": pytest.__version__
            }
        }

        # Send to webhook
        try:
            print(f"[TestWebAppReporter] Sending results to {self.webhook_url}")
            response = httpx.post(
                self.webhook_url,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            print(f"[TestWebAppReporter] Results sent successfully: {response.status_code}")
        except Exception as e:
            print(f"[TestWebAppReporter] Failed to send results: {e}")

    def _extract_test_id(self, nodeid: str) -> str:
        """
        Extract test ID from pytest nodeid
        Example: tests/e2e/linux/test_linux.py::test_L01 -> L01
        """
        if "::" in nodeid:
            parts = nodeid.split("::")
            func_name = parts[-1]
            # Extract test ID from function name (e.g., test_L01 -> L01)
            if "_" in func_name:
                return func_name.split("_")[-1]
        return nodeid


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--run-id",
        action="store",
        default=None,
        help="Test run ID for reporting to test-webapp"
    )
    parser.addoption(
        "--webhook-url",
        action="store",
        default="http://localhost:8001/webhook/pytest-results",
        help="Webhook URL for reporting results"
    )


def pytest_configure(config):
    """Register the custom reporter plugin"""
    if config.getoption("--run-id"):
        reporter = TestWebAppReporter(config)
        config.pluginmanager.register(reporter, "test_webapp_reporter")


# Shared Fixtures

@pytest.fixture(scope="session")
def remediation_engine_url():
    """URL of the remediation engine API"""
    return os.getenv("REMEDIATION_ENGINE_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def api_client(remediation_engine_url):
    """HTTP client for API calls"""
    return httpx.Client(base_url=remediation_engine_url, timeout=30.0)


@pytest.fixture
async def async_api_client(remediation_engine_url):
    """Async HTTP client for API calls"""
    async with httpx.AsyncClient(base_url=remediation_engine_url, timeout=30.0) as client:
        yield client


@pytest.fixture
def auth_token(api_client):
    """
    Authenticate and get JWT token
    Uses default admin credentials
    """
    response = api_client.post(
        "/api/auth/login",
        json={
            "username": os.getenv("TEST_USERNAME", "admin"),
            "password": os.getenv("TEST_PASSWORD", "admin123")
        }
    )

    if response.status_code == 200:
        return response.json().get("access_token")

    # If login fails, return None
    print(f"Authentication failed: {response.status_code}")
    return None


@pytest.fixture
def auth_headers(auth_token):
    """Headers with authentication token"""
    if auth_token:
        return {"Authorization": f"Bearer {auth_token}"}
    return {}


@pytest.fixture(autouse=True)
def test_info(request):
    """
    Automatically print test information before each test
    """
    print(f"\n{'='*80}")
    print(f"Test: {request.node.name}")
    print(f"File: {request.node.fspath}")
    print(f"{'='*80}")
    yield
    print(f"{'='*80}\n")
