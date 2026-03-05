"""
Unit tests for PostmortemService.
"""
import json
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
    return alert


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

    # Executions call returns empty
    empty_result = MagicMock()
    empty_result.scalars.return_value.all.return_value = []

    svc.db.execute = AsyncMock(side_effect=[alert_result, empty_result])

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

    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = [ex]

    svc.db.execute = AsyncMock(side_effect=[alert_result, exec_result])

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
    """generate() with only alert data produces a valid draft with empty executions."""
    svc = _make_service()
    alert = _make_alert()

    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = alert

    empty_exec = MagicMock()
    empty_exec.scalars.return_value.all.return_value = []

    svc.db.execute = AsyncMock(side_effect=[alert_result, empty_exec])
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

    with patch.object(svc, "_call_llm", new=AsyncMock(return_value=llm_output)):
        report = await svc.generate(alert_id=alert.id, created_by=uuid4())

    assert report.remediation_actions == []
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
