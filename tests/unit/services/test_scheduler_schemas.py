"""
Unit tests for schemas_scheduler.py — ScheduledJobCreate / Update / Response
with multi-server fields added in March 2026.

Test IDs: TC-SCHED-SCH-01 … TC-SCHED-SCH-10
"""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas_scheduler import (
    ScheduledJobCreate,
    ScheduledJobUpdate,
    ScheduledJobResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_cron_payload(**overrides) -> dict:
    base = {
        "runbook_id": str(uuid.uuid4()),
        "name": "Daily Cleanup",
        "schedule_type": "cron",
        "cron_expression": "0 2 * * *",
        "timezone": "UTC",
        "enabled": True,
    }
    base.update(overrides)
    return base


# ===========================================================================
# TC-SCHED-SCH-01  ScheduledJobCreate accepts target_server_ids
# ===========================================================================

@pytest.mark.unit
def test_create_accepts_target_server_ids():
    """TC-SCHED-SCH-01: target_server_ids list is accepted and round-trips."""
    sid1 = str(uuid.uuid4())
    sid2 = str(uuid.uuid4())
    payload = _valid_cron_payload(target_server_ids=[sid1, sid2])

    schema = ScheduledJobCreate(**payload)

    assert schema.target_server_ids == [sid1, sid2]


# ===========================================================================
# TC-SCHED-SCH-02  ScheduledJobCreate accepts target_server_group_ids
# ===========================================================================

@pytest.mark.unit
def test_create_accepts_target_server_group_ids():
    """TC-SCHED-SCH-02: target_server_group_ids list is accepted."""
    gid = str(uuid.uuid4())
    payload = _valid_cron_payload(target_server_group_ids=[gid])

    schema = ScheduledJobCreate(**payload)

    assert schema.target_server_group_ids == [gid]


# ===========================================================================
# TC-SCHED-SCH-03  ScheduledJobCreate defaults to empty lists when omitted
# ===========================================================================

@pytest.mark.unit
def test_create_defaults_empty_server_lists():
    """TC-SCHED-SCH-03: Omitting server list fields defaults to []."""
    schema = ScheduledJobCreate(**_valid_cron_payload())

    assert schema.target_server_ids == []
    assert schema.target_server_group_ids == []


# ===========================================================================
# TC-SCHED-SCH-04  ScheduledJobCreate still accepts legacy target_server_id (UUID)
# ===========================================================================

@pytest.mark.unit
def test_create_legacy_target_server_id():
    """TC-SCHED-SCH-04: Single target_server_id UUID field still works."""
    single_id = uuid.uuid4()
    payload = _valid_cron_payload(target_server_id=str(single_id))

    schema = ScheduledJobCreate(**payload)

    assert schema.target_server_id == single_id


# ===========================================================================
# TC-SCHED-SCH-05  ScheduledJobCreate — invalid schedule_type raises
# ===========================================================================

@pytest.mark.unit
def test_create_invalid_schedule_type_raises():
    """TC-SCHED-SCH-05: schedule_type must be 'cron', 'interval', or 'date'."""
    payload = _valid_cron_payload(schedule_type="daily", cron_expression=None)
    with pytest.raises(ValidationError):
        ScheduledJobCreate(**payload)


# ===========================================================================
# TC-SCHED-SCH-06  ScheduledJobCreate — cron without expression raises
# ===========================================================================

@pytest.mark.unit
def test_create_cron_without_expression_raises():
    """TC-SCHED-SCH-06: cron schedule_type without cron_expression raises."""
    payload = _valid_cron_payload()
    payload["cron_expression"] = None
    with pytest.raises(ValidationError):
        ScheduledJobCreate(**payload)


# ===========================================================================
# TC-SCHED-SCH-07  ScheduledJobCreate — interval without interval_seconds raises
# ===========================================================================

@pytest.mark.unit
def test_create_interval_without_seconds_raises():
    """TC-SCHED-SCH-07: interval schedule_type without interval_seconds raises."""
    payload = {
        "runbook_id": str(uuid.uuid4()),
        "name": "Interval Job",
        "schedule_type": "interval",
        "timezone": "UTC",
    }
    with pytest.raises(ValidationError):
        ScheduledJobCreate(**payload)


# ===========================================================================
# TC-SCHED-SCH-08  ScheduledJobUpdate — partial update with server lists
# ===========================================================================

@pytest.mark.unit
def test_update_partial_server_lists():
    """TC-SCHED-SCH-08: ScheduledJobUpdate allows partial update of server lists."""
    sid = str(uuid.uuid4())
    schema = ScheduledJobUpdate(target_server_ids=[sid])

    assert schema.target_server_ids == [sid]
    assert schema.name is None  # other fields untouched


# ===========================================================================
# TC-SCHED-SCH-09  ScheduledJobUpdate — clearing server lists with empty list
# ===========================================================================

@pytest.mark.unit
def test_update_can_clear_server_lists():
    """TC-SCHED-SCH-09: ScheduledJobUpdate allows clearing server lists to []."""
    schema = ScheduledJobUpdate(
        target_server_ids=[],
        target_server_group_ids=[],
    )
    assert schema.target_server_ids == []
    assert schema.target_server_group_ids == []


# ===========================================================================
# TC-SCHED-SCH-10  ScheduledJobResponse — new fields included in response
# ===========================================================================

@pytest.mark.unit
def test_response_includes_multi_server_fields():
    """TC-SCHED-SCH-10: ScheduledJobResponse serialises target_server_ids and group_ids."""
    now = datetime.now(timezone.utc)
    sid = str(uuid.uuid4())
    gid = str(uuid.uuid4())

    response = ScheduledJobResponse(
        id=uuid.uuid4(),
        runbook_id=uuid.uuid4(),
        runbook_name="My Runbook",
        name="Test Schedule",
        description=None,
        schedule_type="cron",
        cron_expression="0 * * * *",
        interval_seconds=None,
        start_date=None,
        end_date=None,
        timezone="UTC",
        target_server_id=None,
        target_server_ids=[sid],
        target_server_group_ids=[gid],
        server_hostname=None,
        execution_params=None,
        max_instances=1,
        misfire_grace_time=300,
        enabled=True,
        last_run_at=None,
        last_run_status=None,
        next_run_at=None,
        run_count=0,
        failure_count=0,
        created_by=None,
        created_at=now,
        updated_at=now,
    )

    data = response.model_dump()
    assert data["target_server_ids"] == [sid]
    assert data["target_server_group_ids"] == [gid]
