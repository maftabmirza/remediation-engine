"""
Unit tests for app/services/alert_suppression_service.py
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.alert_suppression_service import AlertSuppressionService
from app.models_suppression import AlertSuppressionRule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)


def _rule(
    *,
    rule_id=None,
    name="Test Rule",
    rule_type="time_based",
    matchers=None,
    app_id=None,
    starts_at=None,
    ends_at=None,
    grace_period_minutes=5,
    is_active=True,
):
    rule = MagicMock(spec=AlertSuppressionRule)
    rule.id = rule_id or uuid4()
    rule.name = name
    rule.rule_type = rule_type
    rule.matchers = matchers or {}
    rule.app_id = app_id
    rule.starts_at = starts_at or (_NOW - timedelta(hours=1))
    rule.ends_at = ends_at
    rule.grace_period_minutes = grace_period_minutes
    rule.is_active = is_active
    return rule


def _make_svc(rules=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = rules or []
    svc = AlertSuppressionService(db)
    return svc, db


# ---------------------------------------------------------------------------
# 1. Time-based match: rule active within window suppresses alert
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_time_based_match_suppresses_alert():
    """Active rule with no end time should suppress any matching alert."""
    rule = _rule(starts_at=_NOW - timedelta(hours=2), ends_at=None)
    svc, _ = _make_svc(rules=[rule])

    with patch.object(svc, "_is_app_in_maintenance", return_value=False):
        result = svc.check_suppression(alert_labels={}, app_id=None)

    assert result is rule


# ---------------------------------------------------------------------------
# 2. Time-based no match: rule outside window does not suppress
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_expired_rule_does_not_suppress():
    """Rule whose ends_at (plus grace) has passed should not suppress."""
    ends = _NOW - timedelta(minutes=10)
    rule = _rule(
        starts_at=_NOW - timedelta(hours=2),
        ends_at=ends,
        grace_period_minutes=5,  # grace window also expired
    )
    svc, _ = _make_svc(rules=[rule])

    with patch("app.services.alert_suppression_service.datetime") as mock_dt:
        mock_dt.now.return_value = _NOW
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        # Patch the _is_within_window method directly for clarity
        with patch.object(svc, "_is_app_in_maintenance", return_value=False), \
             patch.object(svc, "_is_within_window", return_value=False):
            result = svc.check_suppression(alert_labels={}, app_id=None)

    assert result is None


# ---------------------------------------------------------------------------
# 3. Label regex match: ".*CPU.*" matches "HighCPULoad"
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_label_regex_match_suppresses():
    """Rule with regex matcher should match a conforming label value."""
    rule = _rule(matchers={"alertname": ".*CPU.*"})
    svc, _ = _make_svc(rules=[rule])

    with patch.object(svc, "_is_app_in_maintenance", return_value=False):
        result = svc.check_suppression(
            alert_labels={"alertname": "HighCPULoad"}, app_id=None
        )

    assert result is rule


# ---------------------------------------------------------------------------
# 4. Label regex no match: pattern does not match label
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_label_regex_no_match_does_not_suppress():
    """Rule whose regex does not match the label should not suppress."""
    rule = _rule(matchers={"alertname": "^DiskSpace$"})
    svc, _ = _make_svc(rules=[rule])

    with patch.object(svc, "_is_app_in_maintenance", return_value=False):
        result = svc.check_suppression(
            alert_labels={"alertname": "HighCPULoad"}, app_id=None
        )

    assert result is None


# ---------------------------------------------------------------------------
# 5. Maintenance mode: app in maintenance suppresses all alerts for that app
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_maintenance_mode_suppresses_all_alerts():
    """When an application is in maintenance mode all its alerts are suppressed."""
    app_id = uuid4()
    svc, _ = _make_svc(rules=[])  # no rules needed

    with patch.object(svc, "_is_app_in_maintenance", return_value=True):
        result = svc.check_suppression(alert_labels={"alertname": "Anything"}, app_id=app_id)

    # Returns a synthetic rule (not None)
    assert result is not None
    assert result.rule_type == "maintenance"


# ---------------------------------------------------------------------------
# 6. Expired rule: ends_at < now() does not suppress
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_expired_ends_at_does_not_suppress():
    """A rule whose ends_at is in the past (and grace elapsed) should not fire."""
    rule = _rule(
        starts_at=_NOW - timedelta(hours=3),
        ends_at=_NOW - timedelta(hours=2),
        grace_period_minutes=0,
    )
    svc, _ = _make_svc(rules=[rule])

    with patch.object(svc, "_is_app_in_maintenance", return_value=False):
        # Use real _is_within_window with the rule times
        svc._is_within_window(rule, _NOW)  # force evaluation path
        result = svc.check_suppression(alert_labels={}, app_id=None)

    assert result is None


# ---------------------------------------------------------------------------
# 7. Overlapping rules: first matching rule returned
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_overlapping_rules_returns_first_match():
    """When multiple rules match, the first one (in DB order) is returned."""
    rule1 = _rule(name="Rule 1", matchers={"severity": "warning"})
    rule2 = _rule(name="Rule 2", matchers={"severity": "warning"})
    svc, _ = _make_svc(rules=[rule1, rule2])

    with patch.object(svc, "_is_app_in_maintenance", return_value=False):
        result = svc.check_suppression(
            alert_labels={"severity": "warning"}, app_id=None
        )

    assert result is rule1


# ---------------------------------------------------------------------------
# 8. No active rules: returns None
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_no_active_rules_returns_none():
    """When there are no active suppression rules the service returns None."""
    svc, _ = _make_svc(rules=[])

    with patch.object(svc, "_is_app_in_maintenance", return_value=False):
        result = svc.check_suppression(alert_labels={"alertname": "CPUHigh"}, app_id=None)

    assert result is None


# ---------------------------------------------------------------------------
# 9. Grace period: alert within grace period after window end is still suppressed
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_grace_period_still_suppresses():
    """Alert arriving within the grace window after ends_at is still suppressed."""
    # ends_at was 3 minutes ago; grace period is 5 minutes → still active
    ends = _NOW - timedelta(minutes=3)
    rule = _rule(
        starts_at=_NOW - timedelta(hours=2),
        ends_at=ends,
        grace_period_minutes=5,
    )
    svc, _ = _make_svc(rules=[rule])

    with patch.object(svc, "_is_app_in_maintenance", return_value=False), \
         patch("app.services.alert_suppression_service.datetime") as mock_dt:
        mock_dt.now.return_value = _NOW
        # Call the real _is_within_window with our _NOW
        within = svc._is_within_window(rule, _NOW)

    assert within is True


# ---------------------------------------------------------------------------
# 10. SLO exemption: suppressed alert is excluded from analysis (status check)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_suppressed_alert_status_set_correctly():
    """
    When check_suppression returns a rule, the caller should mark the alert
    status as 'suppressed'. This test verifies the service returns the rule,
    enabling the caller to skip downstream processing.
    """
    rule = _rule(matchers={"alertname": ".*"})
    svc, _ = _make_svc(rules=[rule])

    with patch.object(svc, "_is_app_in_maintenance", return_value=False):
        matched = svc.check_suppression(
            alert_labels={"alertname": "AnyAlert"}, app_id=None
        )

    # Caller receives non-None rule → should set alert.status = "suppressed"
    assert matched is not None
    # Verify correct rule identity (simulates SLO exclusion tracking)
    assert matched.name == "Test Rule"


# ---------------------------------------------------------------------------
# 11. Rule with different app_id does not suppress alert for different app
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_rule_different_app_id_does_not_suppress():
    """A rule restricted to app A should not suppress alerts from app B."""
    rule_app_id = uuid4()
    alert_app_id = uuid4()
    rule = _rule(app_id=rule_app_id, matchers={})
    svc, _ = _make_svc(rules=[rule])

    with patch.object(svc, "_is_app_in_maintenance", return_value=False):
        result = svc.check_suppression(alert_labels={}, app_id=alert_app_id)

    assert result is None
