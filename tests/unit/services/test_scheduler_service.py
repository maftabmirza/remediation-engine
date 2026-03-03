"""
Unit tests for scheduler_service.py — focusing on the multi-server execution
feature added in March 2026.

Test IDs: TC-SCHED-SVC-01 … TC-SCHED-SVC-12
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.models_scheduler import ScheduledJob


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(
    target_server_id: Optional[uuid.UUID] = None,
    target_server_ids: Optional[list] = None,
    target_server_group_ids: Optional[list] = None,
    schedule_type: str = "cron",
    cron_expression: str = "0 * * * *",
    timezone_str: str = "UTC",
) -> ScheduledJob:
    """Build a ScheduledJob instance without hitting the DB."""
    job = ScheduledJob()
    job.id = uuid.uuid4()
    job.runbook_id = uuid.uuid4()
    job.name = "Test Schedule"
    job.description = None
    job.schedule_type = schedule_type
    job.cron_expression = cron_expression
    job.interval_seconds = None
    job.start_date = None
    job.end_date = None
    job.timezone = timezone_str
    job.target_server_id = target_server_id
    job.target_server_ids = target_server_ids or []
    job.target_server_group_ids = target_server_group_ids or []
    job.execution_params = None
    job.max_instances = 1
    job.misfire_grace_time = 300
    job.enabled = True
    job.run_count = 0
    job.failure_count = 0
    job.created_at = datetime.now(timezone.utc)
    job.updated_at = datetime.now(timezone.utc)
    return job


# ===========================================================================
# TC-SCHED-SVC-01  SchedulerService.add_schedule passes server_ids/group_ids
#                  to APScheduler kwargs
# ===========================================================================

@pytest.mark.unit
def test_add_schedule_passes_multi_server_kwargs():
    """TC-SCHED-SVC-01: add_schedule includes server_ids and group_ids in kwargs."""
    from app.services.scheduler_service import SchedulerService

    svc = SchedulerService.__new__(SchedulerService)
    mock_scheduler = MagicMock()
    added_kwargs: dict = {}

    def _capture_add_job(*args, **kwargs):
        # APScheduler.add_job call — capture kwargs dict
        added_kwargs.update(kwargs.get("kwargs", {}))
        mock_job = MagicMock()
        mock_job.next_run_time = None
        return mock_job

    mock_scheduler.add_job.side_effect = _capture_add_job
    mock_scheduler.get_job.return_value = MagicMock(next_run_time=None)
    svc._scheduler = mock_scheduler

    sid1 = str(uuid.uuid4())
    sid2 = str(uuid.uuid4())
    gid1 = str(uuid.uuid4())

    job = _make_job(target_server_ids=[sid1, sid2], target_server_group_ids=[gid1])

    import asyncio
    asyncio.get_event_loop().run_until_complete(svc.add_schedule(job))

    assert added_kwargs.get("server_ids") == [sid1, sid2], "server_ids not forwarded"
    assert added_kwargs.get("group_ids") == [gid1], "group_ids not forwarded"
    assert added_kwargs.get("runbook_id") == str(job.runbook_id)


# ===========================================================================
# TC-SCHED-SVC-02  add_schedule falls back to legacy server_id when lists empty
# ===========================================================================

@pytest.mark.unit
def test_add_schedule_legacy_server_id_still_forwarded():
    """TC-SCHED-SVC-02: Legacy target_server_id is still forwarded as server_id."""
    from app.services.scheduler_service import SchedulerService

    svc = SchedulerService.__new__(SchedulerService)
    mock_scheduler = MagicMock()
    added_kwargs: dict = {}

    def _capture(*args, **kwargs):
        added_kwargs.update(kwargs.get("kwargs", {}))
        return MagicMock(next_run_time=None)

    mock_scheduler.add_job.side_effect = _capture
    mock_scheduler.get_job.return_value = MagicMock(next_run_time=None)
    svc._scheduler = mock_scheduler

    legacy_id = uuid.uuid4()
    job = _make_job(target_server_id=legacy_id)

    import asyncio
    asyncio.get_event_loop().run_until_complete(svc.add_schedule(job))

    assert added_kwargs.get("server_id") == str(legacy_id)
    assert added_kwargs.get("server_ids") == []
    assert added_kwargs.get("group_ids") == []


# ===========================================================================
# TC-SCHED-SVC-03  _execute_scheduled_runbook — single server creates 1 execution
# ===========================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_single_server_creates_one_execution():
    """TC-SCHED-SVC-03: Single server_id results in exactly one RunbookExecution."""
    from app.services import scheduler_service as svc_module

    runbook_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    server_id = str(uuid.uuid4())

    mock_runbook = MagicMock()
    mock_runbook.version = 1
    mock_runbook.steps = [MagicMock()]
    mock_runbook.approval_required = False
    mock_runbook.default_server_id = None

    added_executions = []

    async def _fake_db():
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_runbook
        db.execute.return_value = mock_result

        def _add(obj):
            added_executions.append(obj)

        db.add = MagicMock(side_effect=_add)
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        yield db

    with patch.object(svc_module, "get_async_db", _fake_db), \
         patch.object(svc_module, "update", MagicMock(return_value=MagicMock())):

        from app.models_scheduler import ScheduleExecutionHistory
        from app.models_remediation import RunbookExecution

        await svc_module._execute_scheduled_runbook(
            scheduled_job_id=job_id,
            runbook_id=runbook_id,
            server_id=server_id,
        )

    executions = [obj for obj in added_executions if hasattr(obj, "runbook_id")]
    assert len(executions) == 1, f"Expected 1 execution, got {len(executions)}"


# ===========================================================================
# TC-SCHED-SVC-04  _execute_scheduled_runbook — multiple server_ids creates N executions
# ===========================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_multiple_server_ids_creates_n_executions():
    """TC-SCHED-SVC-04: N server_ids results in N RunbookExecution records."""
    from app.services import scheduler_service as svc_module

    runbook_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    server_ids = [str(uuid.uuid4()) for _ in range(3)]

    mock_runbook = MagicMock()
    mock_runbook.version = 1
    mock_runbook.steps = [MagicMock()]
    mock_runbook.approval_required = False
    mock_runbook.default_server_id = None

    added_executions = []

    async def _fake_db():
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_runbook
        db.execute.return_value = mock_result
        db.add = MagicMock(side_effect=lambda obj: added_executions.append(obj))
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        yield db

    with patch.object(svc_module, "get_async_db", _fake_db), \
         patch.object(svc_module, "update", MagicMock(return_value=MagicMock())):

        await svc_module._execute_scheduled_runbook(
            scheduled_job_id=job_id,
            runbook_id=runbook_id,
            server_ids=server_ids,
        )

    from app.models_remediation import RunbookExecution
    executions = [obj for obj in added_executions if isinstance(obj, RunbookExecution)]
    assert len(executions) == 3, f"Expected 3 executions, got {len(executions)}"


# ===========================================================================
# TC-SCHED-SVC-05  _execute_scheduled_runbook — deduplication of server_ids
# ===========================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_deduplicates_server_ids():
    """TC-SCHED-SVC-05: Duplicate server IDs are deduplicated before execution."""
    from app.services import scheduler_service as svc_module

    runbook_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    # Same server listed twice
    server_ids = [sid, sid]

    mock_runbook = MagicMock()
    mock_runbook.version = 1
    mock_runbook.steps = []
    mock_runbook.approval_required = False
    mock_runbook.default_server_id = None

    added_executions = []

    async def _fake_db():
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_runbook
        db.execute.return_value = mock_result
        db.add = MagicMock(side_effect=lambda obj: added_executions.append(obj))
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        yield db

    with patch.object(svc_module, "get_async_db", _fake_db), \
         patch.object(svc_module, "update", MagicMock(return_value=MagicMock())):

        await svc_module._execute_scheduled_runbook(
            scheduled_job_id=job_id,
            runbook_id=runbook_id,
            server_ids=server_ids,
        )

    from app.models_remediation import RunbookExecution
    executions = [obj for obj in added_executions if isinstance(obj, RunbookExecution)]
    assert len(executions) == 1, "Duplicate server_id should produce only 1 execution"


# ===========================================================================
# TC-SCHED-SVC-06  _execute_scheduled_runbook — fallback to None (runbook default)
# ===========================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_no_server_falls_back_to_runbook_default():
    """TC-SCHED-SVC-06: No server selection falls back to runbook.default_server_id."""
    from app.services import scheduler_service as svc_module

    runbook_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    default_sid = uuid.uuid4()

    mock_runbook = MagicMock()
    mock_runbook.version = 1
    mock_runbook.steps = []
    mock_runbook.approval_required = False
    mock_runbook.default_server_id = default_sid

    added_executions = []

    async def _fake_db():
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_runbook
        db.execute.return_value = mock_result
        db.add = MagicMock(side_effect=lambda obj: added_executions.append(obj))
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        yield db

    with patch.object(svc_module, "get_async_db", _fake_db), \
         patch.object(svc_module, "update", MagicMock(return_value=MagicMock())):

        await svc_module._execute_scheduled_runbook(
            scheduled_job_id=job_id,
            runbook_id=runbook_id,
        )

    from app.models_remediation import RunbookExecution
    executions = [obj for obj in added_executions if isinstance(obj, RunbookExecution)]
    assert len(executions) == 1
    assert executions[0].server_id == default_sid


# ===========================================================================
# TC-SCHED-SVC-07  _execute_scheduled_runbook — missing runbook records failure
# ===========================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_missing_runbook_records_failure():
    """TC-SCHED-SVC-07: Non-existent runbook_id records a 'failed' history entry."""
    from app.services import scheduler_service as svc_module

    added_histories = []

    async def _fake_db():
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # runbook not found
        db.execute.return_value = mock_result
        db.add = MagicMock(side_effect=lambda obj: added_histories.append(obj))
        db.commit = AsyncMock()
        yield db

    with patch.object(svc_module, "get_async_db", _fake_db), \
         patch.object(svc_module, "update", MagicMock(return_value=MagicMock())):

        await svc_module._execute_scheduled_runbook(
            scheduled_job_id=str(uuid.uuid4()),
            runbook_id=str(uuid.uuid4()),
        )

    from app.models_scheduler import ScheduleExecutionHistory
    history_entries = [h for h in added_histories if isinstance(h, ScheduleExecutionHistory)]
    assert len(history_entries) >= 1
    assert history_entries[0].status == "failed"


# ===========================================================================
# TC-SCHED-SVC-08  SchedulerService._create_trigger — cron
# ===========================================================================

@pytest.mark.unit
def test_create_trigger_cron():
    """TC-SCHED-SVC-08: CronTrigger is returned for cron schedule type."""
    from app.services.scheduler_service import SchedulerService
    from apscheduler.triggers.cron import CronTrigger

    svc = SchedulerService.__new__(SchedulerService)
    job = _make_job(schedule_type="cron", cron_expression="0 2 * * *")

    trigger = svc._create_trigger(job)
    assert isinstance(trigger, CronTrigger)


# ===========================================================================
# TC-SCHED-SVC-09  SchedulerService._create_trigger — interval
# ===========================================================================

@pytest.mark.unit
def test_create_trigger_interval():
    """TC-SCHED-SVC-09: IntervalTrigger is returned for interval schedule type."""
    from app.services.scheduler_service import SchedulerService
    from apscheduler.triggers.interval import IntervalTrigger

    svc = SchedulerService.__new__(SchedulerService)
    job = _make_job(schedule_type="interval")
    job.interval_seconds = 3600

    trigger = svc._create_trigger(job)
    assert isinstance(trigger, IntervalTrigger)


# ===========================================================================
# TC-SCHED-SVC-10  SchedulerService._create_trigger — invalid cron raises
# ===========================================================================

@pytest.mark.unit
def test_create_trigger_invalid_cron_raises():
    """TC-SCHED-SVC-10: Invalid cron expression raises ValueError."""
    from app.services.scheduler_service import SchedulerService

    svc = SchedulerService.__new__(SchedulerService)
    job = _make_job(schedule_type="cron", cron_expression="not-a-cron")

    with pytest.raises(ValueError):
        svc._create_trigger(job)


# ===========================================================================
# TC-SCHED-SVC-11  _execute_scheduled_runbook — group_id expansion
# ===========================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_group_ids_expand_to_members():
    """TC-SCHED-SVC-11: group_ids are resolved to member server IDs."""
    from app.services import scheduler_service as svc_module

    runbook_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    gid = str(uuid.uuid4())
    member1 = uuid.uuid4()
    member2 = uuid.uuid4()

    mock_runbook = MagicMock()
    mock_runbook.version = 1
    mock_runbook.steps = []
    mock_runbook.approval_required = False
    mock_runbook.default_server_id = None

    call_count = [0]
    added_executions = []

    async def _fake_db():
        db = AsyncMock()

        async def _execute(stmt):
            # Group expansion runs FIRST, runbook fetch runs SECOND
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                # Group membership query — return member server IDs
                mock_result.scalars.return_value.all.return_value = [member1, member2]
            else:
                # Runbook fetch
                mock_result.scalar_one_or_none.return_value = mock_runbook
            return mock_result

        db.execute.side_effect = _execute
        db.add = MagicMock(side_effect=lambda obj: added_executions.append(obj))
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        yield db

    with patch.object(svc_module, "get_async_db", _fake_db), \
         patch.object(svc_module, "update", MagicMock(return_value=MagicMock())):

        await svc_module._execute_scheduled_runbook(
            scheduled_job_id=job_id,
            runbook_id=runbook_id,
            group_ids=[gid],
        )

    from app.models_remediation import RunbookExecution
    executions = [obj for obj in added_executions if isinstance(obj, RunbookExecution)]
    # Should have 2 executions — one per group member
    assert len(executions) == 2, f"Expected 2 executions from group, got {len(executions)}"


# ===========================================================================
# TC-SCHED-SVC-12  _execute_scheduled_runbook — server_ids + group_ids combined
# ===========================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_combined_server_ids_and_groups():
    """TC-SCHED-SVC-12: server_ids and group_ids are merged and deduplicated."""
    from app.services import scheduler_service as svc_module

    runbook_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    direct_sid = str(uuid.uuid4())
    group_member_sid = str(uuid.uuid4())
    gid = str(uuid.uuid4())

    mock_runbook = MagicMock()
    mock_runbook.version = 1
    mock_runbook.steps = []
    mock_runbook.approval_required = False
    mock_runbook.default_server_id = None

    call_count = [0]
    added_executions = []

    async def _fake_db():
        db = AsyncMock()

        async def _execute(stmt):
            # Group expansion runs FIRST, runbook fetch runs SECOND
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                # Group membership query — return one group member
                mock_result.scalars.return_value.all.return_value = [uuid.UUID(group_member_sid)]
            else:
                # Runbook fetch
                mock_result.scalar_one_or_none.return_value = mock_runbook
            return mock_result

        db.execute.side_effect = _execute
        db.add = MagicMock(side_effect=lambda obj: added_executions.append(obj))
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        yield db

    with patch.object(svc_module, "get_async_db", _fake_db), \
         patch.object(svc_module, "update", MagicMock(return_value=MagicMock())):

        await svc_module._execute_scheduled_runbook(
            scheduled_job_id=job_id,
            runbook_id=runbook_id,
            server_ids=[direct_sid],
            group_ids=[gid],
        )

    from app.models_remediation import RunbookExecution
    executions = [obj for obj in added_executions if isinstance(obj, RunbookExecution)]
    # 1 direct + 1 from group = 2 total (no overlap)
    assert len(executions) == 2, f"Expected 2 combined executions, got {len(executions)}"
