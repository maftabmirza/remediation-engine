"""
Unit tests for PostmortemService.
"""
from importlib import import_module
import json
from pathlib import Path
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException


def _utc(offset_minutes: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)


def _make_alert(name: str = "HighCPU", fired_at=None):
    alert = MagicMock()
    alert.id = uuid4()
    alert.alert_name = name
    alert.severity = "critical"
    alert.instance = "server-01"
    alert.timestamp = fired_at or _utc(-60)
    alert.annotations_json = {"summary": "CPU over 90%"}
    alert.labels_json = {"env": "production"}
    alert.status = "resolved"
    alert.correlation_id = None
    alert.cluster_id = None
    return alert


def _make_incident(status: str = "resolved", eligible: bool = True):
    incident = MagicMock()
    incident.id = uuid4()
    incident.title = "High CPU on server-01"
    incident.status = status
    incident.severity = "critical"
    incident.started_at = _utc(-90)
    incident.resolved_at = _utc(-30) if status == "resolved" else None
    incident.grace_period_ends_at = _utc(-1) if eligible else _utc(+30)
    incident.is_eligible_for_postmortem = eligible
    incident.affected_services = ["node_exporter"]
    return incident


def _make_execution(alert_id, started_offset=-50, completed_offset=-40):
    ex = MagicMock()
    ex.id = uuid4()
    ex.alert_id = alert_id
    ex.runbook_id = uuid4()
    ex.status = "success"
    ex.started_at = _utc(started_offset)
    ex.completed_at = _utc(completed_offset)
    ex.step_executions = []
    return ex


def _make_service():
    """Create a PostmortemService with a mocked AsyncSession."""
    from app.services.postmortem_service import PostmortemService

    db = AsyncMock()
    return PostmortemService(db)


def _make_terminal_session(recording_path: str = "/tmp/terminal.log"):
    session = MagicMock()
    session.id = uuid4()
    session.started_at = _utc(-20)
    session.ended_at = _utc(-10)
    session.recording_path = recording_path
    session.server_credential_id = uuid4()
    session.server = MagicMock()
    session.server.hostname = "74.208.225.85"
    return session


def _patch_incident_service():
    incident_module = import_module("app.services.incident_service")
    return patch.object(incident_module, "IncidentService")


# ---------------------------------------------------------------------------
# Test: alert not found → 404
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_alert_not_found():
    """generate() raises HTTP 404 when the alert does not exist."""
    svc = _make_service()
    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = None
    svc.db.execute = AsyncMock(return_value=alert_result)

    with pytest.raises(HTTPException) as exc_info:
        await svc.generate(alert_id=uuid4(), created_by=uuid4())

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Test: LLM failure → 502
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_llm_failure_raises_502():
    """generate() raises HTTP 502 when the LLM call fails."""
    svc = _make_service()

    alert = _make_alert()
    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = alert
    no_existing_report = MagicMock()
    no_existing_report.scalar_one_or_none.return_value = None
    incident = _make_incident()
    evidence = {
        "incident": incident,
        "alerts": [alert],
        "timeline": [],
        "runbook_executions": [],
        "incident_metrics": [],
        "analysis_feedback": [],
        "execution_outcomes": [],
        "agent_sessions": [],
        "change_events": [],
        "itsm_event": None,
        "affected_services": incident.affected_services,
        "mttr_minutes": 60.0,
    }

    svc.db.execute = AsyncMock(side_effect=[alert_result, no_existing_report])

    with _patch_incident_service() as MockIncSvc:
        mock_inc_svc = MockIncSvc.return_value
        mock_inc_svc.find_or_create_incident_for_alert = AsyncMock(return_value=incident)
        mock_inc_svc.get_evidence = AsyncMock(return_value=evidence)

        with patch.object(svc, "_call_llm", new=AsyncMock(side_effect=HTTPException(status_code=502, detail="LLM error"))):
            with pytest.raises(HTTPException) as exc_info:
                await svc.generate(alert_id=alert.id, created_by=uuid4())
            assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# Test: full data → all sections populated, timeline sorted
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_with_full_data_populates_all_sections():
    """generate() with alert + executions populates all report sections."""
    svc = _make_service()

    alert = _make_alert()
    ex = _make_execution(alert.id)

    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = alert
    no_existing_report = MagicMock()
    no_existing_report.scalar_one_or_none.return_value = None
    incident = _make_incident()
    evidence = {
        "incident": incident,
        "alerts": [alert],
        "timeline": [],
        "runbook_executions": [ex],
        "incident_metrics": [],
        "analysis_feedback": [],
        "execution_outcomes": [],
        "agent_sessions": [],
        "change_events": [],
        "itsm_event": None,
        "affected_services": incident.affected_services,
        "mttr_minutes": 60.0,
    }

    svc.db.execute = AsyncMock(side_effect=[alert_result, no_existing_report])

    llm_output = {
        "impact_summary": "Service degraded for 10 minutes.",
        "root_cause": "Memory leak in the application pod.",
        "contributing_factors": ["High traffic", "Missing resource limits"],
        "lessons_learned": "Add resource limits to all pods.",
        "action_items": [
            {"description": "Add memory limits", "owner": "team-infra", "due_date": None, "status": "open"}
        ],
    }

    svc.db.add = MagicMock()
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    with _patch_incident_service() as MockIncSvc:
        mock_inc_svc = MockIncSvc.return_value
        mock_inc_svc.find_or_create_incident_for_alert = AsyncMock(return_value=incident)
        mock_inc_svc.get_evidence = AsyncMock(return_value=evidence)

        with patch.object(svc, "_call_llm", new=AsyncMock(return_value=llm_output)):
            report = await svc.generate(alert_id=alert.id, created_by=uuid4())

    assert report.impact_summary == "Service degraded for 10 minutes."
    assert report.root_cause == "Memory leak in the application pod."
    assert "High traffic" in report.contributing_factors
    assert report.lessons_learned == "Add resource limits to all pods."
    assert report.status == "draft"
    assert report.generated_by == "ai"


# ---------------------------------------------------------------------------
# Test: partial data — only alert, no executions
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_with_partial_data_no_executions():
    """generate() with only alert data produces a valid draft with manual remediation fallback."""
    svc = _make_service()
    alert = _make_alert()

    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = alert
    no_existing_report = MagicMock()
    no_existing_report.scalar_one_or_none.return_value = None
    incident = _make_incident()
    evidence = {
        "incident": incident,
        "alerts": [alert],
        "timeline": [],
        "runbook_executions": [],
        "incident_metrics": [],
        "analysis_feedback": [],
        "execution_outcomes": [],
        "agent_sessions": [],
        "change_events": [],
        "itsm_event": None,
        "affected_services": incident.affected_services,
        "mttr_minutes": 60.0,
    }

    svc.db.execute = AsyncMock(side_effect=[alert_result, no_existing_report])
    svc.db.add = MagicMock()
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    llm_output = {
        "impact_summary": "Minimal impact.",
        "root_cause": "Unknown.",
        "contributing_factors": [],
        "lessons_learned": "",
        "action_items": [],
    }

    with _patch_incident_service() as MockIncSvc:
        mock_inc_svc = MockIncSvc.return_value
        mock_inc_svc.find_or_create_incident_for_alert = AsyncMock(return_value=incident)
        mock_inc_svc.get_evidence = AsyncMock(return_value=evidence)

        with patch.object(svc, "_call_llm", new=AsyncMock(return_value=llm_output)):
            report = await svc.generate(alert_id=alert.id, created_by=uuid4())

    assert len(report.remediation_actions) == 1
    assert "manual operator intervention" in report.remediation_actions[0]["action"]
    assert report.status == "draft"


# ---------------------------------------------------------------------------
# Test: add_out_of_band_context appends entry, preserves existing
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_out_of_band_context_appends_preserves_existing():
    """add_out_of_band_context() appends new entry without removing existing ones."""
    from app.schemas_postmortem import OutOfBandContextAdd

    svc = _make_service()

    report = MagicMock()
    report.id = uuid4()
    report.out_of_band_context = [
        {"source": "slack", "content": "Existing note", "timestamp": "2026-03-05T10:00:00Z"}
    ]

    get_result = MagicMock()
    get_result.scalar_one_or_none.return_value = report
    svc.db.execute = AsyncMock(return_value=get_result)
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    new_entry = OutOfBandContextAdd(
        source="vendor",
        content="Vendor confirmed outage",
        timestamp=datetime(2026, 3, 5, 14, 0, 0, tzinfo=timezone.utc),
    )

    updated = await svc.add_out_of_band_context(report.id, new_entry)

    assert len(updated.out_of_band_context) == 2
    sources = {e["source"] for e in updated.out_of_band_context}
    assert "slack" in sources
    assert "vendor" in sources


# ---------------------------------------------------------------------------
# Test: regenerate preserves manual out_of_band_context entries
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_regenerate_preserves_manual_oob_context():
    """regenerate() keeps manual out_of_band_context entries and refreshes AI sections."""
    svc = _make_service()

    alert = _make_alert()
    postmortem_id = uuid4()

    # Existing report with manual oob context
    report = MagicMock()
    report.id = postmortem_id
    report.incident_id = None
    report.alert_id = alert.id
    report.status = "draft"
    report.out_of_band_context = [
        {"source": "slack", "content": "Manual note preserved", "timestamp": "2026-03-05T10:00:00Z"}
    ]
    report.timeline = [
        {"timestamp": "2026-03-05T09:00:00Z", "event": "Alert fired", "source": "alert", "manual": False},
        {"timestamp": "2026-03-05T09:30:00Z", "event": "User note", "source": "manual", "manual": True},
    ]

    report_result = MagicMock()
    report_result.scalar_one_or_none.return_value = report

    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = alert

    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = []

    svc.db.execute = AsyncMock(side_effect=[report_result, alert_result, exec_result])
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    llm_output = {
        "impact_summary": "Refreshed summary.",
        "root_cause": "Refreshed root cause.",
        "contributing_factors": ["Factor A"],
        "lessons_learned": "Refreshed lessons.",
        "action_items": [],
    }

    with patch.object(svc, "_call_llm", new=AsyncMock(return_value=llm_output)):
        updated = await svc.regenerate(postmortem_id)

    # Manual oob context preserved
    assert len(updated.out_of_band_context) == 1
    assert updated.out_of_band_context[0]["source"] == "slack"
    assert updated.impact_summary == "Refreshed summary."


# ---------------------------------------------------------------------------
# Test: publish sets status and reviewed_by
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_publish_sets_status_and_reviewer():
    """publish() sets status='published' and reviewed_by."""
    svc = _make_service()
    reviewer_id = uuid4()

    report = MagicMock()
    report.id = uuid4()
    report.status = "in_review"

    result = MagicMock()
    result.scalar_one_or_none.return_value = report
    svc.db.execute = AsyncMock(return_value=result)
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    updated = await svc.publish(report.id, reviewed_by=reviewer_id)

    assert updated.status == "published"
    assert updated.reviewed_by == reviewer_id


# ---------------------------------------------------------------------------
# Test: MTTD/MTTR calculation
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_gather_incident_data_calculates_mttr():
    """_gather_incident_data() computes mttr_minutes from incident start/end."""
    svc = _make_service()

    fired_at = _utc(-90)
    alert = _make_alert(fired_at=fired_at)

    ex = _make_execution(alert.id, started_offset=-80, completed_offset=-30)

    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = [ex]
    svc.db.execute = AsyncMock(return_value=exec_result)

    gathered = await svc._gather_incident_data(alert)

    mttr = gathered["metrics"].get("mttr_minutes")
    assert mttr is not None
    assert mttr > 0  # fired_at to ex.completed_at = 60 min


# ---------------------------------------------------------------------------
# Test: timeline ordering — events sorted chronologically
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_timeline_sorted_chronologically():
    """Timeline events are sorted by timestamp regardless of insertion order."""
    svc = _make_service()

    fired_at = _utc(-120)
    alert = _make_alert(fired_at=fired_at)

    # Execution started later than fired_at
    ex = _make_execution(alert.id, started_offset=-110, completed_offset=-100)
    step = MagicMock()
    step.started_at = _utc(-105)
    step.step_name = "Restart service"
    step.status = "success"
    step.stdout = None
    ex.step_executions = [step]

    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = [ex]
    svc.db.execute = AsyncMock(return_value=exec_result)

    gathered = await svc._gather_incident_data(alert)
    timeline = gathered["timeline"]

    timestamps = [e["timestamp"] for e in timeline]
    assert timestamps == sorted(timestamps), "Timeline must be sorted chronologically"


# ---------------------------------------------------------------------------
# Test: generate_by_incident — happy path
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_by_incident_happy_path():
    """generate_by_incident() creates a postmortem anchored to an incident."""
    svc = _make_service()
    incident_id = uuid4()

    incident = MagicMock()
    incident.id = incident_id
    incident.title = "High CPU on server-01"
    incident.status = "resolved"
    incident.severity = "critical"
    incident.started_at = _utc(-90)
    incident.resolved_at = _utc(-30)
    incident.grace_period_ends_at = _utc(-1)
    incident.is_eligible_for_postmortem = True
    incident.affected_services = ["node_exporter"]

    evidence = {
        "incident": incident,
        "alerts": [_make_alert()],
        "timeline": [
            {"timestamp": _utc(-90).isoformat(), "event": "Alert fired", "source": "alert", "manual": False}
        ],
        "runbook_executions": [],
        "incident_metrics": [],
        "analysis_feedback": [],
        "execution_outcomes": [],
        "agent_sessions": [],
        "change_events": [],
        "itsm_event": None,
        "affected_services": ["node_exporter"],
        "mttr_minutes": 60.0,
    }

    llm_output = {
        "impact_summary": "Incident impacted server-01 for 60 minutes.",
        "root_cause": "High CPU due to runaway process.",
        "contributing_factors": ["Missing resource limits", "Lack of autoscaling"],
        "lessons_learned": "Add CPU limits and autoscaling policies.",
        "action_items": [
            {"description": "Add CPU limits", "owner": "infra", "due_date": None, "status": "open"}
        ],
    }

    svc.db.add = MagicMock()
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()
    no_existing_report = MagicMock()
    no_existing_report.scalar_one_or_none.return_value = None
    svc.db.execute = AsyncMock(return_value=no_existing_report)

    with _patch_incident_service() as MockIncSvc:
        mock_inc_svc_instance = MockIncSvc.return_value
        mock_inc_svc_instance.get_evidence = AsyncMock(return_value=evidence)

        with patch.object(svc, "_call_llm", new=AsyncMock(return_value=llm_output)):
            report = await svc.generate_by_incident(
                incident_id=incident_id, created_by=uuid4()
            )

    assert report.incident_id == incident_id
    assert report.impact_summary == "Incident impacted server-01 for 60 minutes."
    assert report.status == "draft"
    assert report.generated_by == "ai"
    assert report.severity == "critical"


# ---------------------------------------------------------------------------
# Test: generate (alert compat path) delegates to generate_by_incident
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_alert_compat_delegates_to_incident():
    """generate(alert_id) resolves an incident and calls generate_by_incident."""
    svc = _make_service()
    alert = _make_alert()
    incident_id = uuid4()

    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = alert
    svc.db.execute = AsyncMock(return_value=alert_result)
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    mock_incident = MagicMock()
    mock_incident.id = incident_id

    mock_report = MagicMock()
    mock_report.incident_id = incident_id
    mock_report.alert_id = None

    with _patch_incident_service() as MockIncSvc:
        mock_inc_svc_instance = MockIncSvc.return_value
        mock_inc_svc_instance.find_or_create_incident_for_alert = AsyncMock(
            return_value=mock_incident
        )

        with patch.object(
            svc,
            "generate_by_incident",
            new=AsyncMock(return_value=mock_report),
        ) as mock_gen:
            await svc.generate(alert_id=alert.id, created_by=uuid4())

        mock_gen.assert_called_once_with(
            incident_id=incident_id,
            created_by=mock_gen.call_args.kwargs["created_by"],
            app_id=None,
        )


# ---------------------------------------------------------------------------
# Test: regenerate — incident-first path when incident_id set
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_regenerate_uses_incident_path_when_incident_id_set():
    """regenerate() delegates to _regenerate_by_incident when incident_id is set."""
    svc = _make_service()
    incident_id = uuid4()

    report = MagicMock()
    report.id = uuid4()
    report.incident_id = incident_id
    report.alert_id = None

    result = MagicMock()
    result.scalar_one_or_none.return_value = report
    svc.db.execute = AsyncMock(return_value=result)

    with patch.object(
        svc,
        "_regenerate_by_incident",
        new=AsyncMock(return_value=report),
    ) as mock_regen:
        updated = await svc.regenerate(report.id)

    mock_regen.assert_called_once_with(report)
    assert updated is report


# ---------------------------------------------------------------------------
# Test: generate_by_incident rejects incidents that are not yet eligible
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_by_incident_rejects_ineligible_incident():
    """generate_by_incident() rejects incidents that are not yet eligible."""
    svc = _make_service()
    incident = _make_incident(status="open", eligible=False)
    evidence = {
        "incident": incident,
        "alerts": [],
        "timeline": [],
        "runbook_executions": [],
        "incident_metrics": [],
        "analysis_feedback": [],
        "execution_outcomes": [],
        "agent_sessions": [],
        "change_events": [],
        "itsm_event": None,
        "affected_services": [],
        "mttr_minutes": None,
    }

    with _patch_incident_service() as MockIncSvc:
        mock_inc_svc = MockIncSvc.return_value
        mock_inc_svc.get_evidence = AsyncMock(return_value=evidence)

        with pytest.raises(HTTPException) as exc_info:
            await svc.generate_by_incident(incident.id, created_by=uuid4())

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Test: generate_by_incident rejects duplicates for the same incident
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_by_incident_rejects_duplicate_report():
    """generate_by_incident() rejects duplicate postmortems for the same incident."""
    svc = _make_service()
    incident = _make_incident()
    evidence = {
        "incident": incident,
        "alerts": [],
        "timeline": [],
        "runbook_executions": [],
        "incident_metrics": [],
        "analysis_feedback": [],
        "execution_outcomes": [],
        "agent_sessions": [],
        "change_events": [],
        "itsm_event": None,
        "affected_services": [],
        "mttr_minutes": 60.0,
    }
    existing_report = MagicMock()
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing_report
    svc.db.execute = AsyncMock(return_value=existing_result)

    with _patch_incident_service() as MockIncSvc:
        mock_inc_svc = MockIncSvc.return_value
        mock_inc_svc.get_evidence = AsyncMock(return_value=evidence)

        with pytest.raises(HTTPException) as exc_info:
            await svc.generate_by_incident(incident.id, created_by=uuid4())

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Test: incident regeneration refreshes incident-derived fields
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_regenerate_by_incident_refreshes_metrics_and_window():
    """Incident regeneration refreshes metrics and incident window from fresh evidence."""
    svc = _make_service()
    report = MagicMock()
    report.id = uuid4()
    report.incident_id = uuid4()
    report.out_of_band_context = [
        {"source": "manual", "content": "keep", "timestamp": _utc(-10).isoformat()}
    ]
    report.timeline = [
        {"timestamp": _utc(-50).isoformat(), "event": "User note", "source": "manual", "manual": True}
    ]

    report_result = MagicMock()
    report_result.scalar_one_or_none.return_value = report
    svc.db.execute = AsyncMock(return_value=report_result)
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    incident = _make_incident()
    incident.started_at = _utc(-120)
    incident.resolved_at = _utc(-15)
    incident.severity = "warning"
    evidence = {
        "incident": incident,
        "alerts": [],
        "timeline": [
            {"timestamp": _utc(-120).isoformat(), "event": "Alert fired", "source": "alert", "manual": False}
        ],
        "runbook_executions": [],
        "incident_metrics": [],
        "analysis_feedback": [],
        "execution_outcomes": [],
        "agent_sessions": [],
        "change_events": [],
        "itsm_event": None,
        "affected_services": ["node_exporter"],
        "mttr_minutes": 105.0,
    }
    llm_output = {
        "impact_summary": "Updated summary.",
        "root_cause": "Updated root cause.",
        "contributing_factors": ["Factor A"],
        "lessons_learned": "Updated lessons.",
        "action_items": [],
    }

    with _patch_incident_service() as MockIncSvc:
        mock_inc_svc = MockIncSvc.return_value
        mock_inc_svc.get_evidence = AsyncMock(return_value=evidence)

        with patch.object(svc, "_call_llm", new=AsyncMock(return_value=llm_output)):
            updated = await svc.regenerate(report.id)

    assert updated.metrics["mttr_minutes"] == 105.0
    assert updated.incident_start == incident.started_at
    assert updated.incident_end == incident.resolved_at
    assert updated.severity == "warning"


# ---------------------------------------------------------------------------
# Test: gathered evidence uses current agent session fields in timeline
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_build_gathered_from_evidence_summarizes_agent_sessions_from_created_at():
    """Agent session timeline entries use created_at and current AgentStep fields."""
    svc = _make_service()
    incident = _make_incident()
    session = MagicMock()
    session.created_at = _utc(-20)

    step = MagicMock()
    step.step_type = "command"
    step.content = "apache2ctl configtest"
    session.steps = [step]

    evidence = {
        "incident": incident,
        "alerts": [],
        "timeline": [],
        "runbook_executions": [],
        "change_events": [],
        "agent_sessions": [session],
        "terminal_sessions": [],
        "itsm_event": None,
        "mttr_minutes": 60.0,
    }

    gathered = svc._build_gathered_from_evidence(evidence)

    assert gathered["timeline"]
    assert gathered["timeline"][0]["source"] == "agent_session"
    assert "apache2ctl configtest" in gathered["timeline"][0]["event"]
    assert gathered["remediation_actions"]
    assert "apache2ctl configtest" in gathered["remediation_actions"][0]["action"]


# ---------------------------------------------------------------------------
# Test: gathered evidence falls back to manual recovery action from change events
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_build_gathered_from_evidence_uses_change_event_for_manual_remediation():
    """Resolved incidents with no runbooks or agent sessions still expose a manual recovery action."""
    svc = _make_service()
    incident = _make_incident()

    change_event = MagicMock()
    change_event.change_id = "CHG-APACHE-123"
    change_event.description = "Rollback Apache virtual host change"
    change_event.timestamp = _utc(-40)

    evidence = {
        "incident": incident,
        "alerts": [],
        "timeline": [],
        "runbook_executions": [],
        "change_events": [change_event],
        "agent_sessions": [],
        "terminal_sessions": [],
        "itsm_event": None,
        "mttr_minutes": 60.0,
    }

    gathered = svc._build_gathered_from_evidence(evidence)

    assert gathered["remediation_actions"]
    assert gathered["remediation_actions"][0]["outcome"] == "resolved"
    assert "CHG-APACHE-123" in gathered["remediation_actions"][0]["action"]


# ---------------------------------------------------------------------------
# Test: gathered evidence uses terminal recording commands as real remediation data
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_build_gathered_from_evidence_uses_terminal_recording_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Terminal session recordings are parsed into real remediation actions."""
    svc = _make_service()
    incident = _make_incident()
    recording_path = tmp_path / "terminal.log"
    recording_path.write_text("$ apache2ctl configtest\nSyntax OK\n$ systemctl restart apache2\n", encoding="utf-8")

    terminal_session = _make_terminal_session(str(recording_path))

    class _Settings:
        recording_dir = str(tmp_path)

    monkeypatch.setattr("app.services.postmortem_service.get_settings", lambda: _Settings())

    evidence = {
        "incident": incident,
        "alerts": [],
        "timeline": [],
        "runbook_executions": [],
        "change_events": [],
        "agent_sessions": [],
        "terminal_sessions": [terminal_session],
        "itsm_event": None,
        "mttr_minutes": 60.0,
    }

    gathered = svc._build_gathered_from_evidence(evidence)

    assert gathered["timeline"]
    assert gathered["timeline"][0]["source"] == "terminal_session"
    assert "apache2ctl configtest" in gathered["timeline"][0]["event"]
    assert gathered["remediation_actions"]
    assert "apache2ctl configtest" in gathered["remediation_actions"][0]["action"]
    assert "systemctl restart apache2" in gathered["remediation_actions"][0]["action"]
