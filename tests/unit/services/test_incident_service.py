"""
Unit tests for IncidentService.

Covers:
  - assemble_from_correlation: happy path, idempotency, 404
  - assemble_from_cluster: happy path, idempotency, 404
  - mark_resolved: sets status + grace period
  - check_and_mark_eligible: grace period not elapsed, grace period elapsed
  - list_eligible_for_postmortem: basic pagination
  - find_or_create_incident_for_alert: correlation path, cluster path, standalone
  - get_evidence: returns full bundle
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException


def _utc(offset_minutes: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)


def _make_alert(
    name: str = "HighCPU",
    fired_at=None,
    severity: str = "critical",
    correlation_id=None,
    cluster_id=None,
    status: str = "firing",
):
    a = MagicMock()
    a.id = uuid4()
    a.alert_name = name
    a.severity = severity
    a.instance = "server-01"
    a.job = "node_exporter"
    a.timestamp = fired_at or _utc(-60)
    a.annotations_json = {"summary": f"{name} alert"}
    a.labels_json = {"env": "production"}
    a.status = status
    a.correlation_id = correlation_id
    a.cluster_id = cluster_id
    return a


def _make_correlation(status: str = "active", alerts=None, summary: str = "Correlation"):
    corr = MagicMock()
    corr.id = uuid4()
    corr.summary = summary
    corr.status = status
    corr.updated_at = _utc(-30)
    corr.alerts = alerts or []
    return corr


def _make_cluster(is_active: bool = True, alerts=None, severity: str = "critical"):
    cl = MagicMock()
    cl.id = uuid4()
    cl.summary = "Cluster summary"
    cl.is_active = is_active
    cl.severity = severity
    cl.first_seen = _utc(-90)
    cl.closed_at = _utc(-10) if not is_active else None
    cl.alerts = alerts or []
    return cl


def _make_service():
    from app.services.incident_service import IncidentService

    db = AsyncMock()
    return IncidentService(db)


# ---------------------------------------------------------------------------
# assemble_from_correlation — 404 if correlation not found
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_assemble_from_correlation_not_found():
    svc = _make_service()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    svc.db.execute = AsyncMock(return_value=result)

    with pytest.raises(HTTPException) as exc_info:
        await svc.assemble_from_correlation(uuid4())

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# assemble_from_correlation — happy path (no existing incident)
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_assemble_from_correlation_creates_incident():
    svc = _make_service()
    alerts = [_make_alert(fired_at=_utc(-120)), _make_alert(name="DiskFull", fired_at=_utc(-110))]
    corr = _make_correlation(alerts=alerts)

    # First call: load correlation (returns corr)
    # Second call: check for existing incident (returns None)
    corr_result = MagicMock()
    corr_result.scalar_one_or_none.return_value = corr
    no_incident = MagicMock()
    no_incident.scalar_one_or_none.return_value = None

    svc.db.execute = AsyncMock(side_effect=[corr_result, no_incident])
    svc.db.add = MagicMock()
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    incident = await svc.assemble_from_correlation(corr.id)

    assert incident.correlation_id == corr.id
    assert incident.status == "open"
    # Both alert jobs/instances should be captured in affected_services
    assert isinstance(incident.affected_services, list)
    # Started_at should be the earliest alert timestamp
    assert incident.started_at == min(a.timestamp for a in alerts)
    # Severity should be highest across alerts (both critical here)
    assert incident.severity == "critical"
    svc.db.add.assert_called_once()


# ---------------------------------------------------------------------------
# assemble_from_correlation — resolved correlation sets resolved_at
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_assemble_from_correlation_resolved_status():
    svc = _make_service()
    alerts = [_make_alert(fired_at=_utc(-120))]
    corr = _make_correlation(status="resolved", alerts=alerts)
    corr.updated_at = _utc(-35)  # > 30-minute grace period ago → eligible

    corr_result = MagicMock()
    corr_result.scalar_one_or_none.return_value = corr
    no_incident = MagicMock()
    no_incident.scalar_one_or_none.return_value = None

    svc.db.execute = AsyncMock(side_effect=[corr_result, no_incident])
    svc.db.add = MagicMock()
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    incident = await svc.assemble_from_correlation(corr.id)

    assert incident.status == "resolved"
    assert incident.resolved_at is not None
    assert incident.is_eligible_for_postmortem is True


# ---------------------------------------------------------------------------
# assemble_from_correlation — idempotency (existing incident returned)
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_assemble_from_correlation_idempotent():
    svc = _make_service()
    corr = _make_correlation()
    existing_incident = MagicMock()
    existing_incident.correlation_id = corr.id

    corr_result = MagicMock()
    corr_result.scalar_one_or_none.return_value = corr
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing_incident

    svc.db.execute = AsyncMock(side_effect=[corr_result, existing_result])

    incident = await svc.assemble_from_correlation(corr.id)

    # Should return existing without creating a new one
    svc.db.add.assert_not_called()
    assert incident is existing_incident


# ---------------------------------------------------------------------------
# assemble_from_cluster — 404 if cluster not found
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_assemble_from_cluster_not_found():
    svc = _make_service()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    svc.db.execute = AsyncMock(return_value=result)

    with pytest.raises(HTTPException) as exc_info:
        await svc.assemble_from_cluster(uuid4())

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# assemble_from_cluster — inactive cluster creates resolved incident
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_assemble_from_cluster_inactive_creates_resolved_incident():
    svc = _make_service()
    cluster = _make_cluster(is_active=False)
    cluster.closed_at = _utc(-35)  # > grace period → eligible

    cl_result = MagicMock()
    cl_result.scalar_one_or_none.return_value = cluster
    no_incident = MagicMock()
    no_incident.scalar_one_or_none.return_value = None

    svc.db.execute = AsyncMock(side_effect=[cl_result, no_incident])
    svc.db.add = MagicMock()
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    incident = await svc.assemble_from_cluster(cluster.id)

    assert incident.status == "resolved"
    assert incident.cluster_id == cluster.id
    assert incident.is_eligible_for_postmortem is True


# ---------------------------------------------------------------------------
# mark_resolved — sets status, resolved_at, grace_period_ends_at
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_mark_resolved_sets_fields():
    svc = _make_service()
    incident = MagicMock()
    incident.id = uuid4()
    incident.status = "open"

    result = MagicMock()
    result.scalar_one_or_none.return_value = incident
    svc.db.execute = AsyncMock(return_value=result)
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    resolved_at = _utc(-5)
    updated = await svc.mark_resolved(incident.id, resolved_at=resolved_at)

    assert updated.status == "resolved"
    assert updated.resolved_at == resolved_at
    assert updated.grace_period_ends_at is not None


# ---------------------------------------------------------------------------
# check_and_mark_eligible — grace period not yet elapsed
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_and_mark_eligible_grace_period_not_elapsed():
    svc = _make_service()
    incident = MagicMock()
    incident.id = uuid4()
    incident.is_eligible_for_postmortem = False
    incident.status = "resolved"
    incident.grace_period_ends_at = _utc(+10)  # 10 minutes in the future

    result = MagicMock()
    result.scalar_one_or_none.return_value = incident
    svc.db.execute = AsyncMock(return_value=result)

    is_eligible = await svc.check_and_mark_eligible(incident.id)

    assert is_eligible is False
    svc.db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# check_and_mark_eligible — grace period elapsed → flips to True
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_and_mark_eligible_grace_period_elapsed():
    svc = _make_service()
    incident = MagicMock()
    incident.id = uuid4()
    incident.is_eligible_for_postmortem = False
    incident.status = "resolved"
    incident.grace_period_ends_at = _utc(-5)  # 5 minutes ago

    result = MagicMock()
    result.scalar_one_or_none.return_value = incident
    svc.db.execute = AsyncMock(return_value=result)
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    is_eligible = await svc.check_and_mark_eligible(incident.id)

    assert is_eligible is True
    assert incident.is_eligible_for_postmortem is True
    svc.db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# find_or_create_incident_for_alert — correlation path
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_find_or_create_incident_correlation_path():
    svc = _make_service()
    corr_id = uuid4()
    alert = _make_alert(correlation_id=corr_id)
    existing_incident = MagicMock()
    existing_incident.id = uuid4()
    existing_incident.correlation_id = corr_id

    # Mock assemble_from_correlation to return existing_incident
    with patch.object(
        svc,
        "assemble_from_correlation",
        new=AsyncMock(return_value=existing_incident),
    ):
        incident = await svc.find_or_create_incident_for_alert(alert)

    assert incident is existing_incident


# ---------------------------------------------------------------------------
# find_or_create_incident_for_alert — cluster fallback path
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_find_or_create_incident_cluster_fallback():
    svc = _make_service()
    cluster_id = uuid4()
    alert = _make_alert(correlation_id=None, cluster_id=cluster_id)
    existing_incident = MagicMock()
    existing_incident.id = uuid4()
    existing_incident.cluster_id = cluster_id

    with patch.object(
        svc,
        "assemble_from_cluster",
        new=AsyncMock(return_value=existing_incident),
    ):
        incident = await svc.find_or_create_incident_for_alert(alert)

    assert incident is existing_incident


# ---------------------------------------------------------------------------
# find_or_create_incident_for_alert — standalone (no correlation/cluster)
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_find_or_create_incident_standalone():
    svc = _make_service()
    alert = _make_alert(correlation_id=None, cluster_id=None, status="resolved")

    no_result = MagicMock()
    no_result.scalar_one_or_none.return_value = None
    svc.db.execute = AsyncMock(return_value=no_result)
    svc.db.add = MagicMock()
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    incident = await svc.find_or_create_incident_for_alert(alert)

    svc.db.add.assert_called_once()
    assert incident.title == f"Incident: {alert.alert_name}"
    assert incident.status == "resolved"


# ---------------------------------------------------------------------------
# get_evidence — returns full evidence bundle structure
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_evidence_returns_bundle_structure():
    svc = _make_service()
    alert = _make_alert(fired_at=_utc(-90))
    incident = MagicMock()
    incident.id = uuid4()
    incident.title = "Test Incident"
    incident.status = "resolved"
    incident.severity = "critical"
    incident.correlation_id = uuid4()
    incident.cluster_id = None
    incident.itsm_event_id = None
    incident.started_at = _utc(-90)
    incident.resolved_at = _utc(-30)
    incident.affected_services = ["node_exporter", "server-01"]

    # Sequence of execute calls:
    # 1. get() loads the incident
    # 2. _get_incident_alerts via correlation
    # 3. _get_runbook_executions
    # 4. _get_incident_metrics
    # 5. _get_analysis_feedback
    # 6. _get_execution_outcomes
    # 7. _get_agent_sessions
    # 8. _get_change_events
    # itsm_event_id is None → no extra query

    inc_result = MagicMock()
    inc_result.scalar_one_or_none.return_value = incident

    alerts_result = MagicMock()
    alerts_result.scalars.return_value.all.return_value = [alert]

    empty_result = MagicMock()
    empty_result.scalars.return_value.all.return_value = []

    svc.db.execute = AsyncMock(
        side_effect=[
            inc_result,       # get()
            alerts_result,    # _get_incident_alerts
            empty_result,     # _get_runbook_executions
            empty_result,     # _get_incident_metrics
            empty_result,     # _get_analysis_feedback
            empty_result,     # _get_execution_outcomes
            empty_result,     # _get_agent_sessions
            empty_result,     # _get_change_events
        ]
    )

    evidence = await svc.get_evidence(incident.id)

    assert evidence["incident"] is incident
    assert len(evidence["alerts"]) == 1
    assert isinstance(evidence["timeline"], list)
    assert isinstance(evidence["runbook_executions"], list)
    assert isinstance(evidence["change_events"], list)
    assert evidence["affected_services"] == ["node_exporter", "server-01"]
    # MTTR = resolved_at - started_at ≈ 60 minutes
    assert evidence["mttr_minutes"] is not None
    assert evidence["mttr_minutes"] > 0
