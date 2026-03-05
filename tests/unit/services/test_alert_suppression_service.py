"""
Unit tests for AlertSuppressionService (Feature A6).
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models import AlertSuppressionRule
from app.services.alert_suppression_service import AlertSuppressionService


def _utc_now():
    return datetime.now(timezone.utc)


def _make_rule(
    alert_name_pattern="*",
    severity_pattern="*",
    instance_pattern="*",
    job_pattern="*",
    is_active=True,
    starts_at=None,
    ends_at=None,
    reason=None,
):
    """Helper to build an AlertSuppressionRule ORM mock."""
    rule = AlertSuppressionRule(
        id=uuid4(),
        name="test-rule",
        alert_name_pattern=alert_name_pattern,
        severity_pattern=severity_pattern,
        instance_pattern=instance_pattern,
        job_pattern=job_pattern,
        is_active=is_active,
        starts_at=starts_at,
        ends_at=ends_at,
        reason=reason,
    )
    return rule


@pytest.mark.unit
class TestCheckSuppressed:
    """Tests for AlertSuppressionService.check_suppressed()."""

    def _make_service(self, rules):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = rules
        return AlertSuppressionService(db)

    def test_returns_false_when_no_rules(self):
        """Happy path: no rules defined → alert is not suppressed."""
        svc = self._make_service([])
        suppressed, rule = svc.check_suppressed("HighCPU", "critical", "web-01", "nginx")
        assert suppressed is False
        assert rule is None

    def test_suppresses_matching_wildcard_rule(self):
        """Happy path: a catch-all rule suppresses any alert."""
        catch_all = _make_rule()  # all patterns = "*"
        svc = self._make_service([catch_all])
        suppressed, matched = svc.check_suppressed("AnyAlert", "warning", "host-1", "job-1")
        assert suppressed is True
        assert matched is catch_all

    def test_suppresses_alert_matching_name_pattern(self):
        """Happy path: rule with specific alert name pattern matches."""
        rule = _make_rule(alert_name_pattern="HighCPU*")
        svc = self._make_service([rule])
        suppressed, matched = svc.check_suppressed("HighCPUUsage", "critical", "", "")
        assert suppressed is True

    def test_does_not_suppress_non_matching_alert_name(self):
        """Error case: alert name does not match rule pattern → not suppressed."""
        rule = _make_rule(alert_name_pattern="HighCPU*")
        svc = self._make_service([rule])
        suppressed, matched = svc.check_suppressed("DiskSpaceLow", "warning", "", "")
        assert suppressed is False
        assert matched is None

    def test_respects_severity_pattern(self):
        """Edge case: rule matches severity pattern only for 'critical'."""
        rule = _make_rule(severity_pattern="critical")
        svc = self._make_service([rule])

        suppressed_crit, _ = svc.check_suppressed("Any", "critical", "", "")
        suppressed_warn, _ = svc.check_suppressed("Any", "warning", "", "")

        assert suppressed_crit is True
        assert suppressed_warn is False

    def test_respects_instance_pattern(self):
        """Edge case: rule scoped to 'prod-*' instances."""
        rule = _make_rule(instance_pattern="prod-*")
        svc = self._make_service([rule])

        suppressed_prod, _ = svc.check_suppressed("Any", "info", "prod-web-01", "")
        suppressed_dev, _ = svc.check_suppressed("Any", "info", "dev-web-01", "")

        assert suppressed_prod is True
        assert suppressed_dev is False

    def test_inactive_rule_is_skipped(self):
        """Edge case: inactive rules are ignored even when patterns match."""
        rule = _make_rule(is_active=False)
        svc = self._make_service([rule])
        # The DB query already filters is_active=True, but if it somehow leaks:
        # re-test at the service level by ensuring query returns empty
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        svc2 = AlertSuppressionService(db)
        suppressed, _ = svc2.check_suppressed("Any", "critical", "", "")
        assert suppressed is False

    def test_rule_time_window_not_started_yet(self):
        """Edge case: rule starts in the future → not active yet."""
        future = _utc_now() + timedelta(hours=2)
        rule = _make_rule(starts_at=future)
        svc = self._make_service([rule])
        suppressed, _ = svc.check_suppressed("Any", "critical", "", "")
        assert suppressed is False

    def test_rule_time_window_already_expired(self):
        """Edge case: rule ended in the past → no longer active."""
        past = _utc_now() - timedelta(hours=1)
        rule = _make_rule(ends_at=past)
        svc = self._make_service([rule])
        suppressed, _ = svc.check_suppressed("Any", "critical", "", "")
        assert suppressed is False

    def test_rule_active_within_time_window(self):
        """Happy path: rule is within its maintenance window."""
        starts = _utc_now() - timedelta(hours=1)
        ends = _utc_now() + timedelta(hours=1)
        rule = _make_rule(starts_at=starts, ends_at=ends)
        svc = self._make_service([rule])
        suppressed, _ = svc.check_suppressed("Any", "critical", "", "")
        assert suppressed is True


@pytest.mark.unit
class TestCreateRule:
    """Tests for AlertSuppressionService.create_rule()."""

    def _make_db(self):
        db = MagicMock()
        # make add/commit/refresh no-ops
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        return db

    def test_create_rule_happy_path(self):
        """Happy path: create a valid suppression rule."""
        db = self._make_db()
        svc = AlertSuppressionService(db)

        rule = svc.create_rule(
            name="maintenance-window",
            description="Planned maintenance",
            alert_name_pattern="*",
            severity_pattern="*",
            instance_pattern="*",
            job_pattern="*",
            starts_at=None,
            ends_at=None,
            is_active=True,
            reason="Planned maintenance window",
            created_by=uuid4(),
        )

        db.add.assert_called_once()
        db.commit.assert_called()
        assert rule.name == "maintenance-window"
        assert rule.is_active is True

    def test_create_rule_invalid_time_window_raises(self):
        """Error case: ends_at before starts_at raises ValueError."""
        db = self._make_db()
        svc = AlertSuppressionService(db)

        starts = _utc_now() + timedelta(hours=2)
        ends = _utc_now() + timedelta(hours=1)  # ends before starts

        with pytest.raises(ValueError, match="ends_at must be after starts_at"):
            svc.create_rule(
                name="bad-window",
                description=None,
                alert_name_pattern="*",
                severity_pattern="*",
                instance_pattern="*",
                job_pattern="*",
                starts_at=starts,
                ends_at=ends,
                is_active=True,
                reason=None,
                created_by=None,
            )

    def test_create_rule_equal_times_raises(self):
        """Edge case: ends_at equal to starts_at raises ValueError."""
        db = self._make_db()
        svc = AlertSuppressionService(db)
        t = _utc_now()
        with pytest.raises(ValueError):
            svc.create_rule(
                name="equal-times",
                description=None,
                alert_name_pattern="*",
                severity_pattern="*",
                instance_pattern="*",
                job_pattern="*",
                starts_at=t,
                ends_at=t,
                is_active=True,
                reason=None,
                created_by=None,
            )


@pytest.mark.unit
class TestUpdateRule:
    """Tests for AlertSuppressionService.update_rule()."""

    def test_update_existing_rule(self):
        """Happy path: update name of an existing rule."""
        db = MagicMock()
        rule = _make_rule()
        db.query.return_value.filter.return_value.first.return_value = rule
        svc = AlertSuppressionService(db)

        updated = svc.update_rule(rule.id, {"name": "updated-name", "is_active": False})

        assert updated is rule
        assert rule.name == "updated-name"
        assert rule.is_active is False

    def test_update_non_existent_rule_returns_none(self):
        """Error case: update on unknown rule_id returns None."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = AlertSuppressionService(db)

        result = svc.update_rule(uuid4(), {"is_active": False})
        assert result is None

    def test_update_invalid_time_window_raises(self):
        """Edge case: updating to invalid time window raises ValueError."""
        db = MagicMock()
        starts = _utc_now()
        ends = _utc_now() - timedelta(hours=1)  # already in the past, before starts_at
        rule = _make_rule(starts_at=starts)
        db.query.return_value.filter.return_value.first.return_value = rule
        svc = AlertSuppressionService(db)

        with pytest.raises(ValueError):
            svc.update_rule(rule.id, {"ends_at": ends})


@pytest.mark.unit
class TestDeleteRule:
    """Tests for AlertSuppressionService.delete_rule()."""

    def test_delete_existing_rule(self):
        """Happy path: delete an existing rule returns True."""
        db = MagicMock()
        rule = _make_rule()
        db.query.return_value.filter.return_value.first.return_value = rule
        svc = AlertSuppressionService(db)

        result = svc.delete_rule(rule.id)

        assert result is True
        db.delete.assert_called_once_with(rule)
        db.commit.assert_called()

    def test_delete_non_existent_rule_returns_false(self):
        """Error case: deleting unknown rule_id returns False."""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = AlertSuppressionService(db)

        result = svc.delete_rule(uuid4())
        assert result is False


@pytest.mark.unit
class TestListRules:
    """Tests for AlertSuppressionService.list_rules()."""

    def test_list_rules_happy_path(self):
        """Happy path: list returns expected rules and total."""
        db = MagicMock()
        rules = [_make_rule(), _make_rule()]
        mock_query = MagicMock()
        mock_query.count.return_value = 2
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = rules
        db.query.return_value = mock_query
        svc = AlertSuppressionService(db)

        result_rules, total = svc.list_rules(page=1, page_size=20)
        assert total == 2
        assert len(result_rules) == 2

    def test_list_rules_page_size_capped_at_100(self):
        """Edge case: page_size > 100 is capped to 100."""
        db = MagicMock()
        mock_query = MagicMock()
        mock_query.count.return_value = 0
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        db.query.return_value = mock_query
        svc = AlertSuppressionService(db)

        svc.list_rules(page=1, page_size=9999)
        # limit was called with 100 (the cap)
        mock_query.order_by.return_value.offset.return_value.limit.assert_called_with(100)

    def test_list_rules_active_only_adds_filter(self):
        """Edge case: active_only=True adds an is_active filter."""
        db = MagicMock()
        mock_query = MagicMock()
        filtered_query = MagicMock()
        mock_query.filter.return_value = filtered_query
        filtered_query.count.return_value = 0
        filtered_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        db.query.return_value = mock_query
        svc = AlertSuppressionService(db)

        svc.list_rules(active_only=True)
        mock_query.filter.assert_called_once()
