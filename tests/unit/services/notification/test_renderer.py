"""
Unit tests for the notification template renderer.
"""
import pytest


@pytest.mark.unit
class TestRenderer:
    """Tests for render_template()."""

    def test_alert_firing_template(self):
        """alert.firing produces correct title with alert_name substituted."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "alert.firing",
            {"alert_name": "High CPU", "severity": "critical", "source": "prometheus", "description": "90%"},
        )
        assert "High CPU" in msg.title
        assert msg.event_type == "alert.firing"
        assert msg.severity == "critical"

    def test_execution_completed_template(self):
        """execution.completed produces body with runbook_name."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "execution.completed",
            {"runbook_name": "Restart Nginx", "execution_id": "abc-123", "target_host": "web-01"},
        )
        assert "Restart Nginx" in msg.body
        assert msg.event_type == "execution.completed"

    def test_approval_requested_template(self):
        """approval.requested includes expires_at in body."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "approval.requested",
            {"runbook_name": "Reboot Server", "expires_at": "2026-03-04 12:00", "requested_by": "system"},
        )
        assert "Reboot Server" in msg.title
        assert "2026-03-04 12:00" in msg.body

    def test_unknown_event_falls_back_to_generic(self):
        """Unknown event type falls back to 'generic' template."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "custom.internal.event",
            {"title": "Custom Event", "body": "Something happened."},
        )
        assert msg.event_type == "custom.internal.event"
        # Should not raise

    def test_template_key_override(self):
        """Explicit template_key overrides the event type."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "some.event",
            {"alert_name": "Disk Full", "severity": "warning", "source": "src", "description": ""},
            template_key="alert.firing",
        )
        assert "Disk Full" in msg.title

    def test_missing_variables_use_defaults(self):
        """Missing template variables use safe defaults (no KeyError)."""
        from app.services.notification.templates.renderer import render_template

        # Pass empty data — should not raise
        msg = render_template("alert.firing", {})
        assert msg.title  # Not empty
        assert msg.body is not None

    def test_all_template_keys_render_without_error(self):
        """Every defined template key renders without exception."""
        from app.services.notification.templates.renderer import TEMPLATES, render_template

        for key in TEMPLATES:
            msg = render_template(key, {})
            assert msg.event_type == key

    def test_circuit_opened_template(self):
        """circuit.opened template includes runbook_name and failure_count."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "circuit.opened",
            {"runbook_name": "Restart DB", "failure_count": "5", "reset_at": "2026-03-04"},
        )
        assert "Restart DB" in msg.title
        assert "5" in msg.body

    # ---- Dedicated tests for remaining event types ----

    def test_alert_resolved_template(self):
        """alert.resolved substitutes alert_name and duration."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "alert.resolved",
            {"alert_name": "Disk Full", "duration": "15m", "source": "prometheus"},
        )
        assert msg.event_type == "alert.resolved"
        assert "Disk Full" in msg.title
        assert "15m" in msg.body
        assert "prometheus" in msg.body

    def test_alert_analyzed_template(self):
        """alert.analyzed substitutes alert_name and analysis_summary."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "alert.analyzed",
            {"alert_name": "Memory Spike", "severity": "warning", "analysis_summary": "OOM likely"},
        )
        assert msg.event_type == "alert.analyzed"
        assert "Memory Spike" in msg.title
        assert "OOM likely" in msg.body
        assert msg.severity == "warning"

    def test_execution_triggered_template(self):
        """execution.triggered substitutes runbook_name and alert_name."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "execution.triggered",
            {"runbook_name": "Scale Out", "alert_name": "High CPU", "execution_id": "ex-99"},
        )
        assert msg.event_type == "execution.triggered"
        assert "Scale Out" in msg.title
        assert "High CPU" in msg.body
        assert "ex-99" in msg.body

    def test_execution_started_template(self):
        """execution.started substitutes runbook_name and target_host."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "execution.started",
            {"runbook_name": "Restart Nginx", "target_host": "web-02", "execution_id": "ex-01"},
        )
        assert msg.event_type == "execution.started"
        assert "Restart Nginx" in msg.title
        assert "web-02" in msg.body
        assert "ex-01" in msg.body

    def test_execution_failed_template(self):
        """execution.failed substitutes runbook_name, error_message, target_host."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "execution.failed",
            {
                "runbook_name": "DB Failover",
                "target_host": "db-01",
                "error_message": "SSH timeout",
                "execution_id": "ex-55",
            },
        )
        assert msg.event_type == "execution.failed"
        assert "DB Failover" in msg.title
        assert "SSH timeout" in msg.body
        assert "db-01" in msg.body

    def test_execution_step_failed_template(self):
        """execution.step_failed substitutes step_name and error_message."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "execution.step_failed",
            {
                "step_name": "Check disk",
                "runbook_name": "Disk Cleanup",
                "error_message": "Permission denied",
                "execution_id": "ex-77",
            },
        )
        assert msg.event_type == "execution.step_failed"
        assert "Check disk" in msg.title
        assert "Disk Cleanup" in msg.title
        assert "Permission denied" in msg.body

    def test_approval_expired_template(self):
        """approval.expired substitutes runbook_name and execution_id."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "approval.expired",
            {"runbook_name": "Reboot Server", "execution_id": "ex-42"},
        )
        assert msg.event_type == "approval.expired"
        assert "Reboot Server" in msg.title
        assert "ex-42" in msg.body

    def test_schedule_failed_template(self):
        """schedule.failed substitutes job_name, error_message, next_run."""
        from app.services.notification.templates.renderer import render_template

        msg = render_template(
            "schedule.failed",
            {"job_name": "nightly-backup", "error_message": "Disk full", "next_run": "2026-03-05 02:00"},
        )
        assert msg.event_type == "schedule.failed"
        assert "nightly-backup" in msg.title
        assert "Disk full" in msg.body
        assert "2026-03-05 02:00" in msg.body
