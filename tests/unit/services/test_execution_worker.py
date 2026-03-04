"""
Unit tests for ExecutionWorker._execute_runbook notification dispatch.

Ensures that _notify_bg is called with the correct event_type for
every exit path: success, executor failure, early-exit (no runbook,
no server), and exception.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_execution(*, runbook=None, server_id=None, status="approved"):
    """Build a mock RunbookExecution with sensible defaults."""
    ex = MagicMock()
    ex.id = uuid.uuid4()
    ex.status = status
    ex.runbook = runbook
    ex.server_id = server_id
    ex.error_message = None
    ex.started_at = None
    ex.completed_at = None
    return ex


def _make_runbook(name="Test Runbook"):
    rb = MagicMock()
    rb.name = name
    return rb


# ===========================================================================
# Notification dispatch on failure paths
# ===========================================================================

@pytest.mark.unit
class TestExecuteRunbookNotifications:
    """Verify _notify_bg is called on every _execute_runbook exit path."""

    @pytest.mark.asyncio
    async def test_notify_on_runbook_not_found(self):
        """execution.failed notification is sent when runbook is None."""
        from app.services.execution_worker import ExecutionWorker

        execution = _make_execution(runbook=None, server_id=uuid.uuid4())
        db = AsyncMock()

        worker = ExecutionWorker()
        with patch("app.services.execution_worker._notify_bg") as mock_notify:
            await worker._execute_runbook(db, execution)

        # Should have two calls: execution.started + execution.failed
        event_types = [c.args[0] for c in mock_notify.call_args_list]
        assert "execution.started" in event_types
        assert "execution.failed" in event_types
        assert execution.status == "failed"
        assert "Runbook not found" in execution.error_message

    @pytest.mark.asyncio
    async def test_notify_on_no_server(self):
        """execution.failed notification is sent when server_id is None."""
        from app.services.execution_worker import ExecutionWorker

        execution = _make_execution(
            runbook=_make_runbook("My Runbook"),
            server_id=None,
        )
        db = AsyncMock()

        worker = ExecutionWorker()
        with patch("app.services.execution_worker._notify_bg") as mock_notify:
            await worker._execute_runbook(db, execution)

        event_types = [c.args[0] for c in mock_notify.call_args_list]
        assert "execution.started" in event_types
        assert "execution.failed" in event_types
        assert execution.status == "failed"
        assert "No target server specified" in execution.error_message

    @pytest.mark.asyncio
    async def test_notify_on_exception(self):
        """execution.failed notification is sent on unexpected exception."""
        from app.services.execution_worker import ExecutionWorker

        execution = _make_execution(
            runbook=_make_runbook("Crash Runbook"),
            server_id=uuid.uuid4(),
        )
        db = AsyncMock()

        worker = ExecutionWorker()
        # Make RunbookExecutor raise
        with (
            patch("app.services.execution_worker._notify_bg") as mock_notify,
            patch(
                "app.services.execution_worker.RunbookExecutor",
                side_effect=RuntimeError("boom"),
            ),
        ):
            await worker._execute_runbook(db, execution)

        event_types = [c.args[0] for c in mock_notify.call_args_list]
        assert "execution.started" in event_types
        assert "execution.failed" in event_types
        assert execution.status == "failed"

    @pytest.mark.asyncio
    async def test_notify_on_executor_success(self):
        """execution.completed notification on successful execution."""
        from app.services.execution_worker import ExecutionWorker

        execution = _make_execution(
            runbook=_make_runbook("Good Runbook"),
            server_id=uuid.uuid4(),
        )
        db = AsyncMock()

        mock_result = MagicMock()
        mock_result.status = "success"

        mock_executor = AsyncMock()
        mock_executor.execute_runbook = AsyncMock(return_value=mock_result)

        worker = ExecutionWorker()
        with (
            patch("app.services.execution_worker._notify_bg") as mock_notify,
            patch(
                "app.services.execution_worker.RunbookExecutor",
                return_value=mock_executor,
            ),
        ):
            await worker._execute_runbook(db, execution)

        event_types = [c.args[0] for c in mock_notify.call_args_list]
        assert "execution.started" in event_types
        assert "execution.completed" in event_types

    @pytest.mark.asyncio
    async def test_notify_on_executor_failure(self):
        """execution.failed notification when executor returns failure."""
        from app.services.execution_worker import ExecutionWorker

        execution = _make_execution(
            runbook=_make_runbook("Failing Runbook"),
            server_id=uuid.uuid4(),
        )
        db = AsyncMock()

        mock_result = MagicMock()
        mock_result.status = "failed"

        mock_executor = AsyncMock()
        mock_executor.execute_runbook = AsyncMock(return_value=mock_result)

        worker = ExecutionWorker()
        with (
            patch("app.services.execution_worker._notify_bg") as mock_notify,
            patch(
                "app.services.execution_worker.RunbookExecutor",
                return_value=mock_executor,
            ),
        ):
            await worker._execute_runbook(db, execution)

        event_types = [c.args[0] for c in mock_notify.call_args_list]
        assert "execution.started" in event_types
        assert "execution.failed" in event_types

    @pytest.mark.asyncio
    async def test_failed_notify_includes_error_message(self):
        """execution.failed event_data includes the error_message."""
        from app.services.execution_worker import ExecutionWorker

        execution = _make_execution(
            runbook=_make_runbook("Test RB"),
            server_id=None,
        )
        db = AsyncMock()

        worker = ExecutionWorker()
        with patch("app.services.execution_worker._notify_bg") as mock_notify:
            await worker._execute_runbook(db, execution)

        # Find the execution.failed call
        failed_calls = [
            c for c in mock_notify.call_args_list if c.args[0] == "execution.failed"
        ]
        assert len(failed_calls) == 1
        event_data = failed_calls[0].args[1]
        assert "error_message" in event_data
        assert "No target server specified" in event_data["error_message"]
