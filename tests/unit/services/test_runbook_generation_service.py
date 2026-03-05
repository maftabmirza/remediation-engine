"""
Unit tests for RunbookGenerationService (Feature B2).
"""
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


def _utc(offset_minutes: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(
    goal: str = "restart nginx service after high memory usage",
    status: str = "completed",
    created_at: datetime = None,
    completed_at: datetime = None,
) -> MagicMock:
    s = MagicMock()
    s.id = uuid4()
    s.goal = goal
    s.status = status
    s.created_at = created_at or _utc(-120)
    s.completed_at = completed_at or _utc(-60)
    return s


def _make_step(
    content: str = "systemctl restart nginx",
    step_type: str = "command",
    status: str = "executed",
    session_id=None,
) -> MagicMock:
    step = MagicMock()
    step.id = uuid4()
    step.agent_session_id = session_id or uuid4()
    step.content = content
    step.step_type = step_type
    step.status = status
    step.reasoning = "Service needs restart"
    step.output = "Restarted successfully"
    return step


def _make_outcome(session_id=None, success: bool = True) -> MagicMock:
    o = MagicMock()
    o.id = uuid4()
    o.session_id = session_id or uuid4()
    o.success = success
    return o


def _make_blocklist_entry(
    pattern: str,
    pattern_type: str = "contains",
    enabled: bool = True,
) -> MagicMock:
    bl = MagicMock()
    bl.id = uuid4()
    bl.pattern = pattern
    bl.pattern_type = pattern_type
    bl.enabled = enabled
    return bl


def _make_service():
    """Create RunbookGenerationService with a fully mocked AsyncSession."""
    from app.services.runbook_generation_service import RunbookGenerationService

    db = AsyncMock()
    return RunbookGenerationService(db)


# ---------------------------------------------------------------------------
# find_generation_candidates
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_find_candidates_returns_clusters_above_min_count():
    """Clusters with ≥ min_success_count sessions are returned."""
    svc = _make_service()

    sessions = [_make_session() for _ in range(4)]
    outcomes = [_make_outcome(s.id) for s in sessions]

    # Execution: sessions, then outcomes, then steps x4
    steps = [_make_step(session_id=s.id) for s in sessions]

    def _scalars_side_effect(*args, **kwargs):
        r = MagicMock()
        # We need to track call order to return different data
        return r

    # Use AsyncMock with side_effect list for sequential execute() calls
    sessions_result = MagicMock()
    sessions_result.scalars.return_value.all.return_value = sessions

    outcomes_result = MagicMock()
    outcomes_result.scalars.return_value.all.return_value = outcomes

    steps_result = MagicMock()
    steps_result.scalars.return_value.all.return_value = steps

    # Outcomes per cluster
    cluster_outcomes_result = MagicMock()
    cluster_outcomes_result.scalars.return_value.all.return_value = outcomes

    svc.db.execute = AsyncMock(
        side_effect=[
            sessions_result,
            outcomes_result,
            steps_result,
            cluster_outcomes_result,
        ]
    )

    candidates = await svc.find_generation_candidates(min_success_count=3)

    assert len(candidates) >= 1
    assert candidates[0].session_count >= 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_find_candidates_insufficient_sessions_returns_empty():
    """Clusters with < min_success_count sessions are excluded."""
    svc = _make_service()

    # Only 2 sessions — below default threshold of 3
    sessions = [_make_session() for _ in range(2)]
    outcomes = [_make_outcome(s.id) for s in sessions]

    sessions_result = MagicMock()
    sessions_result.scalars.return_value.all.return_value = sessions

    outcomes_result = MagicMock()
    outcomes_result.scalars.return_value.all.return_value = outcomes

    svc.db.execute = AsyncMock(side_effect=[sessions_result, outcomes_result])

    candidates = await svc.find_generation_candidates(min_success_count=3)
    assert candidates == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_find_candidates_no_sessions_returns_empty():
    """When there are no completed sessions, an empty list is returned."""
    svc = _make_service()

    sessions_result = MagicMock()
    sessions_result.scalars.return_value.all.return_value = []

    svc.db.execute = AsyncMock(return_value=sessions_result)

    candidates = await svc.find_generation_candidates()
    assert candidates == []


# ---------------------------------------------------------------------------
# generate_runbook — blocklist violation
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_runbook_blocklist_violation_raises_value_error():
    """Commands matching the blocklist cause ValueError — no runbook is created."""
    svc = _make_service()

    session_id = uuid4()
    steps = [_make_step(content="rm -rf /var/data", session_id=session_id)]
    blocklist = [_make_blocklist_entry("rm")]

    steps_result = MagicMock()
    steps_result.scalars.return_value.all.return_value = steps

    blocklist_result = MagicMock()
    blocklist_result.scalars.return_value.all.return_value = blocklist

    svc.db.execute = AsyncMock(side_effect=[steps_result, blocklist_result])

    # LLM returns a step with "rm" command
    llm_payload = {
        "name": "Cleanup Runbook",
        "description": "Generated runbook",
        "steps": [
            {
                "step_number": 1,
                "name": "Remove old cache",
                "step_type": "command",
                "command_template": "rm -rf /tmp/cache",
                "variables_required": [],
                "rollback_command": None,
                "is_idempotent": False,
            }
        ],
    }

    with patch.object(svc, "_call_llm", new=AsyncMock(return_value=llm_payload)):
        with pytest.raises(ValueError, match="blocklist"):
            await svc.generate_runbook(
                session_ids=[session_id],
                runbook_name=None,
                app_id=None,
                created_by=uuid4(),
            )

    # Ensure no runbook was added to the session
    svc.db.add.assert_not_called()


# ---------------------------------------------------------------------------
# generate_runbook — LLM failure
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_runbook_llm_failure_propagates():
    """LLM exception is propagated; no partial runbook is saved."""
    from fastapi import HTTPException

    svc = _make_service()

    session_id = uuid4()
    steps = [_make_step(content="systemctl restart app", session_id=session_id)]

    steps_result = MagicMock()
    steps_result.scalars.return_value.all.return_value = steps

    svc.db.execute = AsyncMock(return_value=steps_result)

    with patch.object(
        svc,
        "_call_llm",
        new=AsyncMock(side_effect=HTTPException(status_code=502, detail="LLM error")),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await svc.generate_runbook(
                session_ids=[session_id],
                runbook_name=None,
                app_id=None,
                created_by=uuid4(),
            )

    assert exc_info.value.status_code == 502
    svc.db.add.assert_not_called()


# ---------------------------------------------------------------------------
# generate_runbook — successful generation with Jinja2 variables
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_runbook_creates_runbook_with_variables():
    """A successful generation creates a Runbook with Jinja2-templated steps."""
    svc = _make_service()

    session_id = uuid4()
    steps_input = [_make_step(content="systemctl restart nginx", session_id=session_id)]

    steps_result = MagicMock()
    steps_result.scalars.return_value.all.return_value = steps_input

    blocklist_result = MagicMock()
    blocklist_result.scalars.return_value.all.return_value = []

    svc.db.execute = AsyncMock(side_effect=[steps_result, blocklist_result])
    svc.db.flush = AsyncMock()
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    llm_payload = {
        "name": "Service Restart Runbook",
        "description": "Restart a given service",
        "steps": [
            {
                "step_number": 1,
                "name": "Restart service",
                "step_type": "command",
                "command_template": "systemctl restart {{ service_name }}",
                "variables_required": ["service_name"],
                "rollback_command": None,
                "is_idempotent": True,
            }
        ],
    }

    with patch.object(svc, "_call_llm", new=AsyncMock(return_value=llm_payload)):
        runbook = await svc.generate_runbook(
            session_ids=[session_id],
            runbook_name="My Runbook",
            app_id=None,
            created_by=uuid4(),
        )

    # Runbook was added to session and committed
    svc.db.add.assert_called()
    svc.db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# generate_runbook — non-idempotent detection
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_runbook_detects_non_idempotent_command():
    """Commands matching destructive patterns set requires_human_review = True."""
    from app.services.runbook_generation_service import _is_non_idempotent

    assert _is_non_idempotent("rm -rf /tmp/cache") is True
    assert _is_non_idempotent("drop table users") is True
    assert _is_non_idempotent("systemctl restart nginx") is False
    assert _is_non_idempotent("kill -9 1234") is True
    assert _is_non_idempotent("echo hello") is False


# ---------------------------------------------------------------------------
# generate_runbook — variable extraction
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_variable_extraction_from_jinja2_template():
    """_extract_variables correctly extracts all Jinja2 placeholder names."""
    from app.services.runbook_generation_service import _extract_variables

    template = "systemctl restart {{ service_name }} on {{ host }}"
    variables = _extract_variables(template)
    assert "service_name" in variables
    assert "host" in variables
    assert len(variables) == 2

    # No variables
    assert _extract_variables("echo hello") == []

    # Duplicate variables — should deduplicate
    assert _extract_variables("{{ svc }} {{ svc }}") == ["svc"]


# ---------------------------------------------------------------------------
# approve_draft
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_approve_draft_sets_enabled_true():
    """approve_draft sets enabled=True and optionally auto_execute."""
    svc = _make_service()

    runbook_id = uuid4()
    runbook = MagicMock()
    runbook.id = runbook_id
    runbook.enabled = False
    runbook.auto_execute = False

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = runbook
    svc.db.execute = AsyncMock(return_value=result_mock)
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    returned = await svc.approve_draft(
        runbook_id=runbook_id,
        approved_by=uuid4(),
        enable_auto_trigger=True,
    )

    assert runbook.enabled is True
    assert runbook.auto_execute is True
    svc.db.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_approve_draft_not_found_raises_404():
    """approve_draft raises HTTP 404 when runbook does not exist."""
    from fastapi import HTTPException

    svc = _make_service()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    svc.db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(HTTPException) as exc_info:
        await svc.approve_draft(runbook_id=uuid4(), approved_by=uuid4())

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Auto-generated runbooks are inactive by default
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_generated_runbook_is_inactive_by_default():
    """Newly generated runbooks have enabled=False and auto_execute=False."""
    svc = _make_service()

    session_id = uuid4()
    steps_input = [_make_step(content="echo ok", session_id=session_id)]

    steps_result = MagicMock()
    steps_result.scalars.return_value.all.return_value = steps_input

    blocklist_result = MagicMock()
    blocklist_result.scalars.return_value.all.return_value = []

    svc.db.execute = AsyncMock(side_effect=[steps_result, blocklist_result])
    svc.db.flush = AsyncMock()
    svc.db.commit = AsyncMock()
    svc.db.refresh = AsyncMock()

    llm_payload = {
        "name": "Simple Runbook",
        "description": "Test",
        "steps": [
            {
                "step_number": 1,
                "name": "Echo",
                "step_type": "command",
                "command_template": "echo {{ message }}",
                "variables_required": ["message"],
                "rollback_command": None,
                "is_idempotent": True,
            }
        ],
    }

    captured_runbooks: list = []

    original_add = svc.db.add

    def capture_add(obj):
        captured_runbooks.append(obj)
        return original_add(obj)

    svc.db.add = capture_add

    with patch.object(svc, "_call_llm", new=AsyncMock(return_value=llm_payload)):
        await svc.generate_runbook(
            session_ids=[session_id],
            runbook_name=None,
            app_id=None,
            created_by=uuid4(),
        )

    # First added object should be the Runbook (before the steps)
    from app.models_remediation import Runbook

    runbook_objs = [o for o in captured_runbooks if isinstance(o, Runbook)]
    assert len(runbook_objs) >= 1
    rb = runbook_objs[0]
    assert rb.enabled is False
    assert rb.auto_execute is False
    assert rb.source == "auto_generated"
