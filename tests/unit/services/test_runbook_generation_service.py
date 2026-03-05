"""
Unit tests for RunbookGenerationService (Feature B2).

Test IDs: TC-RBG-SVC-01 … TC-RBG-SVC-08
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc(iso: str = "2026-03-01T10:00:00") -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def _make_session(
    session_id: Optional[uuid.UUID] = None,
    status: str = "completed",
    goal: str = "Restart the nginx web service",
    completed_at: Optional[datetime] = None,
) -> MagicMock:
    session = MagicMock()
    session.id = session_id or uuid.uuid4()
    session.status = status
    session.goal = goal
    session.created_at = _utc()
    session.completed_at = completed_at or _utc("2026-03-01T10:15:00")
    session.steps = []
    return session


def _make_step(
    session_id: Optional[uuid.UUID] = None,
    step_type: str = "command",
    content: str = "systemctl restart nginx",
    status: str = "executed",
    reasoning: str = "Restarting nginx to clear stale connections",
    output: str = "Restarted successfully",
) -> MagicMock:
    step = MagicMock()
    step.id = uuid.uuid4()
    step.agent_session_id = session_id or uuid.uuid4()
    step.step_type = step_type
    step.content = content
    step.status = status
    step.reasoning = reasoning
    step.output = output
    return step


def _make_blocklist_entry(
    pattern: str = "rm",
    pattern_type: str = "contains",
    severity: str = "critical",
    enabled: bool = True,
) -> MagicMock:
    entry = MagicMock()
    entry.id = uuid.uuid4()
    entry.pattern = pattern
    entry.pattern_type = pattern_type
    entry.severity = severity
    entry.enabled = enabled
    return entry


def _make_runbook(
    runbook_id: Optional[uuid.UUID] = None,
    name: str = "Auto-Generated Runbook",
    source: str = "auto_generated",
    enabled: bool = False,
    auto_execute: bool = False,
    steps: Optional[List] = None,
) -> MagicMock:
    rb = MagicMock()
    rb.id = runbook_id or uuid.uuid4()
    rb.name = name
    rb.description = "Auto-generated from 3 sessions. Requires human review."
    rb.source = source
    rb.enabled = enabled
    rb.auto_execute = auto_execute
    rb.steps = steps or []
    return rb


# ---------------------------------------------------------------------------
# TC-RBG-SVC-01  Successful generation: sessions → runbook draft created
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_runbook_success():
    """TC-RBG-SVC-01: 3 similar sessions produce a runbook draft."""
    from app.services.runbook_generation_service import RunbookGenerationService

    db = AsyncMock()
    session_ids = [uuid.uuid4() for _ in range(3)]

    # Steps returned from the DB
    steps = [
        _make_step(sid, content="systemctl restart {{ service_name }}")
        for sid in session_ids
    ]

    llm_data = {
        "name": "Restart Service Runbook",
        "description": "Restart a Linux service",
        "steps": [
            {
                "step_number": 1,
                "name": "Restart service",
                "step_type": "command",
                "command_template": "systemctl restart {{ service_name }}",
                "variables_required": ["service_name"],
                "is_idempotent": True,
            }
        ],
    }

    # DB side-effect: first call returns steps, second returns empty blocklist
    steps_result = MagicMock()
    steps_result.scalars.return_value.all.return_value = steps

    empty_result = MagicMock()
    empty_result.scalars.return_value.all.return_value = []

    call_count = 0

    async def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return steps_result
        return empty_result

    db.execute = AsyncMock(side_effect=side_effect_execute)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()

    svc = RunbookGenerationService(db)

    with patch.object(
        RunbookGenerationService,
        "_call_llm_for_generation",
        new_callable=AsyncMock,
        return_value=llm_data,
    ):
        result = await svc.generate_runbook(
            session_ids=session_ids,
            runbook_name="Test Runbook",
            app_id=None,
            created_by=uuid.uuid4(),
        )

    assert result is not None
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# TC-RBG-SVC-02  Blocklist violation: ValueError raised, no runbook saved
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_runbook_blocklist_violation():
    """TC-RBG-SVC-02: Command matching blocklist raises ValueError, no runbook saved."""
    from app.services.runbook_generation_service import RunbookGenerationService

    db = AsyncMock()
    session_ids = [uuid.uuid4()]

    steps = [_make_step(session_ids[0], content="rm -rf /var/cache")]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = steps

    blocklist_entry = _make_blocklist_entry(pattern="rm", pattern_type="contains")
    blocklist_result = MagicMock()
    blocklist_result.scalars.return_value.all.return_value = [blocklist_entry]

    call_count = 0

    async def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_result
        return blocklist_result

    db.execute = AsyncMock(side_effect=side_effect_execute)
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    llm_response = {
        "name": "Dangerous Runbook",
        "description": "Removes cache",
        "steps": [
            {
                "step_number": 1,
                "name": "Remove cache",
                "step_type": "command",
                "command_template": "rm -rf /var/cache",
                "variables_required": [],
                "is_idempotent": False,
            }
        ],
    }

    svc = RunbookGenerationService(db)
    with patch.object(
        RunbookGenerationService,
        "_call_llm_for_generation",
        new_callable=AsyncMock,
        return_value=llm_response,
    ):
        with pytest.raises(ValueError, match="blocked pattern"):
            await svc.generate_runbook(
                session_ids=session_ids,
                runbook_name=None,
                app_id=None,
                created_by=uuid.uuid4(),
            )

    # Runbook must NOT have been created
    db.flush.assert_not_awaited()
    db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# TC-RBG-SVC-03  Insufficient sessions: empty candidates
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_find_candidates_insufficient_sessions():
    """TC-RBG-SVC-03: Clusters with < min_success_count not returned."""
    from app.services.runbook_generation_service import RunbookGenerationService

    db = AsyncMock()

    # Only 2 completed sessions with the same goal
    sessions = [_make_session(goal="restart nginx") for _ in range(2)]
    for s in sessions:
        step = _make_step(s.id)
        s.steps = [step]

    mock_sessions_result = MagicMock()
    mock_sessions_result.scalars.return_value.all.return_value = sessions

    mock_outcomes_result = MagicMock()
    # Both sessions have successful outcomes
    outcomes = []
    for s in sessions:
        o = MagicMock()
        o.session_id = s.id
        o.success = True
        outcomes.append(o)
    mock_outcomes_result.scalars.return_value.all.return_value = outcomes

    call_count = 0

    async def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_sessions_result
        return mock_outcomes_result

    db.execute = AsyncMock(side_effect=side_effect_execute)

    svc = RunbookGenerationService(db)
    candidates = await svc.find_generation_candidates(min_success_count=3)

    assert candidates == []


# ---------------------------------------------------------------------------
# TC-RBG-SVC-04  LLM failure: exception propagated, no partial runbook
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_runbook_llm_failure():
    """TC-RBG-SVC-04: LLM exception propagates; no runbook is persisted."""
    from app.services.runbook_generation_service import RunbookGenerationService

    db = AsyncMock()
    session_ids = [uuid.uuid4()]

    steps = [_make_step(session_ids[0])]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = steps
    db.execute = AsyncMock(return_value=mock_result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    svc = RunbookGenerationService(db)
    with patch.object(
        RunbookGenerationService,
        "_call_llm_for_generation",
        new_callable=AsyncMock,
        side_effect=RuntimeError("LLM unavailable"),
    ):
        with pytest.raises(RuntimeError, match="LLM unavailable"):
            await svc.generate_runbook(
                session_ids=session_ids,
                runbook_name=None,
                app_id=None,
                created_by=uuid.uuid4(),
            )

    db.flush.assert_not_awaited()
    db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# TC-RBG-SVC-05  Variable extraction from template
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_extract_jinja2_variables():
    """TC-RBG-SVC-05: Variables correctly extracted from Jinja2 templates."""
    from app.services.runbook_generation_service import _extract_jinja2_variables

    template = "systemctl restart {{ service_name }}"
    variables = _extract_jinja2_variables(template)

    assert variables == ["service_name"]


@pytest.mark.unit
def test_extract_jinja2_variables_multiple():
    """Variables: multiple unique variables extracted and sorted."""
    from app.services.runbook_generation_service import _extract_jinja2_variables

    template = "ssh {{ user }}@{{ host }} -p {{ port }}"
    variables = _extract_jinja2_variables(template)

    assert "user" in variables
    assert "host" in variables
    assert "port" in variables
    assert variables == sorted(variables)


# ---------------------------------------------------------------------------
# TC-RBG-SVC-06  Non-idempotent pattern detection
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_non_idempotent_detection():
    """TC-RBG-SVC-06: rm -rf flagged as non-idempotent."""
    from app.services.runbook_generation_service import _is_non_idempotent

    assert _is_non_idempotent("rm -rf /tmp/cache") is True
    assert _is_non_idempotent("systemctl restart nginx") is False
    assert _is_non_idempotent("DROP TABLE users") is True
    assert _is_non_idempotent("echo hello") is False


@pytest.mark.unit
def test_build_step_previews_requires_review():
    """Non-idempotent commands produce requires_human_review=True."""
    from app.services.runbook_generation_service import RunbookGenerationService

    steps_data = [
        {
            "step_number": 1,
            "name": "Remove temp",
            "step_type": "command",
            "command_template": "rm -rf /tmp/cache",
            "is_idempotent": None,
        }
    ]
    previews = RunbookGenerationService.build_step_previews(steps_data)

    assert len(previews) == 1
    assert previews[0].requires_human_review is True
    assert previews[0].is_idempotent is False


# ---------------------------------------------------------------------------
# TC-RBG-SVC-07  approve_draft: is_active (enabled) set to True
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_approve_draft_sets_enabled():
    """TC-RBG-SVC-07: approve_draft sets enabled=True."""
    from app.services.runbook_generation_service import RunbookGenerationService

    db = AsyncMock()
    runbook_id = uuid.uuid4()

    runbook = _make_runbook(runbook_id=runbook_id)
    runbook.enabled = False
    runbook.auto_execute = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = runbook
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    svc = RunbookGenerationService(db)
    result = await svc.approve_draft(
        runbook_id=runbook_id,
        approved_by=uuid.uuid4(),
        enable_auto_trigger=False,
    )

    assert result.enabled is True
    assert result.auto_execute is False
    db.commit.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_approve_draft_with_auto_trigger():
    """approve_draft with enable_auto_trigger=True sets auto_execute=True."""
    from app.services.runbook_generation_service import RunbookGenerationService

    db = AsyncMock()
    runbook_id = uuid.uuid4()

    runbook = _make_runbook(runbook_id=runbook_id)
    runbook.enabled = False
    runbook.auto_execute = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = runbook
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    svc = RunbookGenerationService(db)
    result = await svc.approve_draft(
        runbook_id=runbook_id,
        approved_by=uuid.uuid4(),
        enable_auto_trigger=True,
    )

    assert result.enabled is True
    assert result.auto_execute is True


# ---------------------------------------------------------------------------
# TC-RBG-SVC-08  find_generation_candidates: min_success_count enforced
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_find_candidates_returns_qualifying_clusters():
    """TC-RBG-SVC-08: Clusters >= min_success_count returned, others excluded."""
    from app.services.runbook_generation_service import RunbookGenerationService

    db = AsyncMock()

    # 4 sessions with identical goal (should form 1 cluster)
    goal = "restart nginx service after config change"
    sessions = [_make_session(goal=goal) for _ in range(4)]
    for s in sessions:
        step = _make_step(s.id)
        s.steps = [step]

    mock_sessions_result = MagicMock()
    mock_sessions_result.scalars.return_value.all.return_value = sessions

    mock_outcomes_result = MagicMock()
    outcomes = []
    for s in sessions:
        o = MagicMock()
        o.session_id = s.id
        o.success = True
        outcomes.append(o)
    mock_outcomes_result.scalars.return_value.all.return_value = outcomes

    call_count = 0

    async def side_effect_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_sessions_result
        return mock_outcomes_result

    db.execute = AsyncMock(side_effect=side_effect_execute)

    svc = RunbookGenerationService(db)
    candidates = await svc.find_generation_candidates(min_success_count=3)

    assert len(candidates) >= 1
    assert candidates[0].session_count == 4
