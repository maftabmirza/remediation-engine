"""
Unit tests for PostmortemService.

Test IDs: TC-PM-SVC-01 … TC-PM-SVC-09
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.schemas_postmortem import OutOfBandContextAdd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def _make_alert(
    alert_id: Optional[uuid.UUID] = None,
    name: str = "HighCPU",
    severity: str = "critical",
    fired_at: Optional[datetime] = None,
    app_id: Optional[uuid.UUID] = None,
    correlation_id: Optional[uuid.UUID] = None,
) -> MagicMock:
    alert = MagicMock()
    alert.id = alert_id or uuid.uuid4()
    alert.alert_name = name
    alert.severity = severity
    alert.timestamp = fired_at or _utc("2026-03-01T10:00:00")
    alert.app_id = app_id
    alert.correlation_id = correlation_id
    alert.status = "firing"
    alert.instance = "web-01"
    alert.labels_json = {}
    alert.annotations_json = {}
    return alert


def _make_report(
    report_id: Optional[uuid.UUID] = None,
    status: str = "draft",
    alert_id: Optional[uuid.UUID] = None,
    timeline: Optional[List] = None,
    out_of_band_context: Optional[List] = None,
) -> MagicMock:
    report = MagicMock()
    report.id = report_id or uuid.uuid4()
    report.status = status
    report.alert_id = alert_id or uuid.uuid4()
    report.timeline = timeline or []
    report.out_of_band_context = out_of_band_context or []
    report.impact_summary = "Impact"
    report.root_cause = "Root cause"
    report.contributing_factors = ["factor1"]
    report.action_items = []
    report.lessons_learned = "Lessons"
    report.metrics = {}
    report.incident_start = None
    report.incident_end = None
    return report


def _llm_response_json(**kwargs) -> str:
    data = {
        "impact_summary": kwargs.get("impact_summary", "Service degraded for 30 minutes."),
        "root_cause": kwargs.get("root_cause", "Memory leak in worker process."),
        "contributing_factors": kwargs.get("contributing_factors", ["factor1", "factor2", "factor3"]),
        "lessons_learned": kwargs.get("lessons_learned", "Improve memory monitoring."),
        "action_items": kwargs.get(
            "action_items",
            [
                {"description": "Fix memory leak", "owner": "team-a", "due_date": None, "status": "open"},
                {"description": "Add alerting", "owner": None, "due_date": None, "status": "open"},
                {"description": "Update runbook", "owner": "sre", "due_date": None, "status": "open"},
            ],
        ),
    }
    return json.dumps(data)


# ---------------------------------------------------------------------------
# TC-PM-SVC-01  Full generation: all sections populated, timeline sorted
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_full_data():
    """TC-PM-SVC-01: Generation with full data populates all sections."""
    from app.services.postmortem_service import PostmortemService

    alert_id = uuid.uuid4()
    created_by = uuid.uuid4()
    alert = _make_alert(alert_id=alert_id)

    db = AsyncMock()
    svc = PostmortemService(db)

    # Mock _load_alert
    svc._load_alert = AsyncMock(return_value=alert)

    # Mock _gather_incident_data
    gathered: Dict[str, Any] = {
        "alert": {
            "id": str(alert_id),
            "name": "HighCPU",
            "severity": "critical",
            "instance": "web-01",
            "status": "firing",
            "fired_at": "2026-03-01T10:00:00+00:00",
            "labels": {},
            "annotations": {},
        },
        "correlated_alerts": [],
        "executions": [
            {
                "runbook_id": str(uuid.uuid4()),
                "status": "success",
                "started_at": "2026-03-01T10:05:00+00:00",
                "completed_at": "2026-03-01T10:10:00+00:00",
                "duration_minutes": 5.0,
                "result_summary": "Fixed",
                "steps": [],
            }
        ],
        "metrics": {
            "mttd_minutes": 5.0,
            "mtta_minutes": 2.0,
            "mtte_minutes": 3.0,
            "mttr_minutes": 15.0,
            "incident_started": "2026-03-01T10:00:00+00:00",
            "incident_resolved": "2026-03-01T10:20:00+00:00",
        },
        "feedback": [],
        "remediation_actions": [
            {"action": "Executed runbook", "runbook_id": str(uuid.uuid4()), "outcome": "success", "duration_minutes": 5.0}
        ],
    }
    svc._gather_incident_data = AsyncMock(return_value=gathered)

    # Mock LLM call
    svc._call_llm = AsyncMock(return_value={
        "impact_summary": "Service degraded.",
        "root_cause": "Memory leak.",
        "contributing_factors": ["factor1", "factor2"],
        "lessons_learned": "Improve monitoring.",
        "action_items": [
            {"description": "Fix leak", "owner": "team-a", "due_date": None, "status": "open"}
        ],
    })

    saved_reports = []

    def _add(obj):
        saved_reports.append(obj)

    db.add = _add
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    report = await svc.generate(alert_id, created_by)

    assert report is not None
    assert report.impact_summary == "Service degraded."
    assert report.root_cause == "Memory leak."
    assert len(report.contributing_factors) == 2
    assert report.lessons_learned == "Improve monitoring."
    assert len(report.action_items) == 1
    assert report.status == "draft"
    assert report.generated_by == "ai"
    assert report.created_by == created_by

    # Timeline must contain alert fired_at entry
    ts_values = [e.get("timestamp") for e in report.timeline]
    assert "2026-03-01T10:00:00+00:00" in ts_values

    # Timeline must be sorted chronologically
    assert ts_values == sorted(ts_values)


# ---------------------------------------------------------------------------
# TC-PM-SVC-02  Partial data: only alert, no executions
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_partial_data():
    """TC-PM-SVC-02: Generation with only alert data (no executions) completes gracefully."""
    from app.services.postmortem_service import PostmortemService

    alert_id = uuid.uuid4()
    created_by = uuid.uuid4()
    alert = _make_alert(alert_id=alert_id)

    db = AsyncMock()
    svc = PostmortemService(db)

    svc._load_alert = AsyncMock(return_value=alert)
    gathered: Dict[str, Any] = {
        "alert": {
            "id": str(alert_id),
            "name": "HighCPU",
            "severity": "critical",
            "instance": "web-01",
            "status": "firing",
            "fired_at": "2026-03-01T10:00:00+00:00",
            "labels": {},
            "annotations": {},
        },
        "correlated_alerts": [],
        "executions": [],
        "metrics": None,
        "feedback": [],
        "remediation_actions": [],
    }
    svc._gather_incident_data = AsyncMock(return_value=gathered)
    svc._call_llm = AsyncMock(return_value={
        "impact_summary": "Brief impact.",
        "root_cause": "Unknown.",
        "contributing_factors": [],
        "lessons_learned": "",
        "action_items": [],
    })

    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    report = await svc.generate(alert_id, created_by)

    assert report.alert_id == alert_id
    assert report.status == "draft"
    assert len(report.timeline) == 1  # Only the alert fired_at entry


# ---------------------------------------------------------------------------
# TC-PM-SVC-03  Alert not found → raises HTTPException 404
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_alert_not_found():
    """TC-PM-SVC-03: Alert not found raises HTTPException 404."""
    from fastapi import HTTPException
    from app.services.postmortem_service import PostmortemService

    db = AsyncMock()
    svc = PostmortemService(db)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await svc.generate(uuid.uuid4(), uuid.uuid4())

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TC-PM-SVC-04  LLM failure → raises HTTPException 502 and does not save
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_llm_failure_raises_502():
    """TC-PM-SVC-04: LLM failure raises 502 and does not commit to DB."""
    from fastapi import HTTPException
    from app.services.postmortem_service import PostmortemService

    alert_id = uuid.uuid4()
    alert = _make_alert(alert_id=alert_id)

    db = AsyncMock()
    svc = PostmortemService(db)

    svc._load_alert = AsyncMock(return_value=alert)
    svc._gather_incident_data = AsyncMock(return_value={
        "alert": {"fired_at": None, "name": "test", "severity": "info"},
        "correlated_alerts": [],
        "executions": [],
        "metrics": None,
        "feedback": [],
        "remediation_actions": [],
    })
    svc._call_llm = AsyncMock(side_effect=HTTPException(status_code=502, detail="LLM error"))

    db.add = MagicMock()
    db.commit = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await svc.generate(alert_id, uuid.uuid4())

    assert exc_info.value.status_code == 502
    # Nothing should have been committed
    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# TC-PM-SVC-05  add_out_of_band_context: entry appended, existing preserved
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_out_of_band_context():
    """TC-PM-SVC-05: New context entry appended, existing entries preserved."""
    from app.services.postmortem_service import PostmortemService

    pm_id = uuid.uuid4()
    existing_oob = [{"source": "slack", "content": "Previous note", "timestamp": "2026-03-01T09:00:00"}]
    report = _make_report(report_id=pm_id, out_of_band_context=list(existing_oob))

    db = AsyncMock()
    svc = PostmortemService(db)
    svc._get_or_404 = AsyncMock(return_value=report)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    entry = OutOfBandContextAdd(source="email", content="Customer report", timestamp=None)
    updated = await svc.add_out_of_band_context(pm_id, entry)

    assert len(updated.out_of_band_context) == 2
    assert updated.out_of_band_context[0]["source"] == "slack"
    assert updated.out_of_band_context[1]["source"] == "email"
    assert updated.out_of_band_context[1]["content"] == "Customer report"


# ---------------------------------------------------------------------------
# TC-PM-SVC-06  regenerate: manual OOB context preserved, AI sections refreshed
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_regenerate_preserves_manual_context():
    """TC-PM-SVC-06: Regenerate preserves manual out-of-band context and refreshes AI sections."""
    from app.services.postmortem_service import PostmortemService

    pm_id = uuid.uuid4()
    alert_id = uuid.uuid4()
    manual_entry = {"source": "customer", "content": "Reported outage", "timestamp": "2026-03-01T11:00:00"}
    manual_timeline = {"timestamp": "2026-03-01T10:15:00", "event": "Manual note", "source": "manual", "manual": True}

    report = _make_report(
        report_id=pm_id,
        alert_id=alert_id,
        timeline=[manual_timeline],
        out_of_band_context=[manual_entry],
    )
    alert = _make_alert(alert_id=alert_id)

    db = AsyncMock()
    svc = PostmortemService(db)

    svc._get_or_404 = AsyncMock(return_value=report)
    svc._load_alert = AsyncMock(return_value=alert)
    svc._gather_incident_data = AsyncMock(return_value={
        "alert": {
            "id": str(alert_id),
            "name": "HighCPU",
            "severity": "critical",
            "instance": "web-01",
            "status": "firing",
            "fired_at": "2026-03-01T10:00:00+00:00",
            "labels": {},
            "annotations": {},
        },
        "correlated_alerts": [],
        "executions": [],
        "metrics": None,
        "feedback": [],
        "remediation_actions": [],
    })
    svc._call_llm = AsyncMock(return_value={
        "impact_summary": "Refreshed impact.",
        "root_cause": "New root cause.",
        "contributing_factors": ["new factor"],
        "lessons_learned": "New lessons.",
        "action_items": [],
    })

    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    updated = await svc.regenerate(pm_id)

    # OOB manual entry preserved
    assert len(updated.out_of_band_context) == 1
    assert updated.out_of_band_context[0]["source"] == "customer"

    # AI sections updated
    assert updated.impact_summary == "Refreshed impact."

    # Manual timeline entry preserved in timeline
    manual_ts_found = any(e.get("manual") for e in updated.timeline)
    assert manual_ts_found


# ---------------------------------------------------------------------------
# TC-PM-SVC-07  publish: status → published, reviewed_by set
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_publish_sets_status_and_reviewer():
    """TC-PM-SVC-07: publish() sets status='published' and reviewed_by."""
    from app.services.postmortem_service import PostmortemService

    pm_id = uuid.uuid4()
    reviewer_id = uuid.uuid4()
    report = _make_report(report_id=pm_id, status="draft")

    db = AsyncMock()
    svc = PostmortemService(db)
    svc._get_or_404 = AsyncMock(return_value=report)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    updated = await svc.publish(pm_id, reviewed_by=reviewer_id)

    assert updated.status == "published"
    assert updated.reviewed_by == reviewer_id


# ---------------------------------------------------------------------------
# TC-PM-SVC-08  MTTD/MTTR calculation from timestamps
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_compute_metrics_from_gathered_data():
    """TC-PM-SVC-08: Metrics computed correctly from gathered IncidentMetrics data."""
    from app.services.postmortem_service import PostmortemService

    db = AsyncMock()
    svc = PostmortemService(db)

    gathered = {
        "metrics": {
            "mttd_minutes": 5.0,
            "mtta_minutes": 2.0,
            "mtte_minutes": 3.0,
            "mttr_minutes": 20.0,
            "incident_started": "2026-03-01T10:00:00+00:00",
            "incident_resolved": "2026-03-01T10:30:00+00:00",
        }
    }

    metrics = svc._compute_metrics(gathered, [])

    assert metrics["mttd_minutes"] == 5.0
    assert metrics["mttr_minutes"] == 20.0


# ---------------------------------------------------------------------------
# TC-PM-SVC-09  Timeline ordering: events sorted chronologically
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_timeline_sorted_chronologically():
    """TC-PM-SVC-09: Timeline entries sorted chronologically regardless of source."""
    from app.services.postmortem_service import PostmortemService

    db = AsyncMock()
    svc = PostmortemService(db)

    # Alert fires at T+0, execution starts at T+5, correlated alert at T+2
    gathered = {
        "alert": {
            "name": "HighCPU",
            "severity": "critical",
            "fired_at": "2026-03-01T10:00:00+00:00",
        },
        "correlated_alerts": [
            {"name": "MemoryHigh", "timestamp": "2026-03-01T10:02:00+00:00"},
        ],
        "executions": [
            {
                "runbook_id": str(uuid.uuid4()),
                "status": "success",
                "started_at": "2026-03-01T10:05:00+00:00",
                "completed_at": "2026-03-01T10:10:00+00:00",
                "steps": [],
            }
        ],
        "metrics": {
            "incident_resolved": "2026-03-01T10:20:00+00:00",
        },
    }

    timeline = svc._build_timeline(gathered)

    timestamps = [e["timestamp"] for e in timeline]
    assert timestamps == sorted(timestamps), f"Timeline not sorted: {timestamps}"

    # Verify expected events are present
    sources = [e["source"] for e in timeline]
    assert "alert" in sources
    assert "correlated_alert" in sources
    assert "runbook_execution" in sources
    assert "incident_metrics" in sources
