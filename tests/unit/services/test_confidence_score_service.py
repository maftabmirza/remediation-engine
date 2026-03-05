"""
Unit tests for ConfidenceScoreService.

Test IDs: TC-CONF-SVC-01 … TC-CONF-SVC-08
"""
import uuid
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas_confidence import ConfidenceScore, SampleOutcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_alert(has_embedding: bool = True) -> MagicMock:
    alert = MagicMock()
    alert.id = uuid.uuid4()
    alert.embedding = MagicMock() if has_embedding else None
    return alert


def _make_outcome(resolution_type: str, time_minutes: Optional[float] = None) -> MagicMock:
    row = MagicMock()
    row.resolution_type = resolution_type
    row.time_to_resolution_minutes = time_minutes
    return row


def _make_similar_row(alert_id: uuid.UUID, similarity: float) -> MagicMock:
    row = MagicMock()
    row.id = alert_id
    row.similarity = similarity
    return row


def _make_execution_row(
    alert_id: uuid.UUID,
    resolution_type: str,
    time_minutes: Optional[float] = None,
) -> MagicMock:
    row = MagicMock()
    row.alert_id = alert_id
    row.resolution_type = resolution_type
    row.time_to_resolution_minutes = time_minutes
    return row


# ---------------------------------------------------------------------------
# TC-CONF-SVC-01  High confidence: many similar alerts, high success rate
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_high_confidence_score():
    """TC-CONF-SVC-01: Mostly successful executions on similar alerts → score ≥ 70."""
    from app.services.confidence_score_service import ConfidenceScoreService

    alert_id = uuid.uuid4()
    runbook_id = uuid.uuid4()

    # Build 5 similar alerts that were all resolved successfully
    similar_ids = [uuid.uuid4() for _ in range(5)]
    similar_rows = [_make_similar_row(aid, 0.9) for aid in similar_ids]
    execution_rows = [
        _make_execution_row(aid, "full", 10.0) for aid in similar_ids
    ]

    db = AsyncMock()
    svc = ConfidenceScoreService(db)

    alert = _make_alert(has_embedding=True)
    alert.id = alert_id
    emb = MagicMock()
    alert.embedding = emb

    async def _execute(query):
        mock_result = MagicMock()
        # First call: load alert
        # Second call: load embedding
        # Third call: load similar alerts
        # Fourth call: load execution outcomes
        # Use call count to differentiate
        _execute._call_count = getattr(_execute, "_call_count", 0) + 1
        n = _execute._call_count

        if n == 1:
            # Alert lookup
            mock_result.scalar_one_or_none.return_value = alert
        elif n == 2:
            # Embedding lookup
            mock_result.first.return_value = (emb,)
        elif n == 3:
            # Similar alerts
            mock_result.all.return_value = similar_rows
        elif n == 4:
            # Execution outcomes
            mock_result.all.return_value = execution_rows
        else:
            mock_result.all.return_value = []
            mock_result.scalar_one_or_none.return_value = None
        return mock_result

    db.execute = _execute

    score = await svc.calculate(alert_id, runbook_id)

    assert score.score >= 70
    assert score.confidence_level == "high"
    assert score.similar_count == 5
    assert score.success_rate > 0.8


# ---------------------------------------------------------------------------
# TC-CONF-SVC-02  Low confidence: many similar alerts, mostly failures
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_low_confidence_score():
    """TC-CONF-SVC-02: Mostly failed executions on similar alerts → score < 40."""
    from app.services.confidence_score_service import ConfidenceScoreService

    alert_id = uuid.uuid4()
    runbook_id = uuid.uuid4()

    similar_ids = [uuid.uuid4() for _ in range(5)]
    similar_rows = [_make_similar_row(aid, 0.85) for aid in similar_ids]
    execution_rows = [
        _make_execution_row(aid, "no_effect") for aid in similar_ids
    ]

    db = AsyncMock()
    svc = ConfidenceScoreService(db)

    alert = _make_alert(has_embedding=True)
    alert.id = alert_id
    emb = MagicMock()
    alert.embedding = emb

    async def _execute(query):
        _execute._call_count = getattr(_execute, "_call_count", 0) + 1
        n = _execute._call_count
        mock_result = MagicMock()
        if n == 1:
            mock_result.scalar_one_or_none.return_value = alert
        elif n == 2:
            mock_result.first.return_value = (emb,)
        elif n == 3:
            mock_result.all.return_value = similar_rows
        elif n == 4:
            mock_result.all.return_value = execution_rows
        else:
            mock_result.all.return_value = []
        return mock_result

    db.execute = _execute

    score = await svc.calculate(alert_id, runbook_id)

    assert score.score < 40
    assert score.confidence_level == "low"


# ---------------------------------------------------------------------------
# TC-CONF-SVC-03  Insufficient data: fewer than 3 similar alerts → blends with prior
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_insufficient_data_blends_with_prior():
    """TC-CONF-SVC-03: <3 similar alerts → score blends with overall effectiveness prior."""
    from app.services.confidence_score_service import ConfidenceScoreService

    alert_id = uuid.uuid4()
    runbook_id = uuid.uuid4()

    # Only 2 similar alerts
    similar_ids = [uuid.uuid4() for _ in range(2)]
    similar_rows = [_make_similar_row(aid, 0.75) for aid in similar_ids]
    execution_rows = [
        _make_execution_row(aid, "full", 5.0) for aid in similar_ids
    ]

    # Prior: 70% success rate (7 full, 3 failures)
    prior_rows = [MagicMock() for _ in range(10)]
    for i, r in enumerate(prior_rows):
        r.resolution_type = "full" if i < 7 else "no_effect"

    db = AsyncMock()
    svc = ConfidenceScoreService(db)

    alert = _make_alert(has_embedding=True)
    alert.id = alert_id
    emb = MagicMock()
    alert.embedding = emb

    call_count = [0]

    async def _execute(query):
        call_count[0] += 1
        n = call_count[0]
        mock_result = MagicMock()
        if n == 1:
            mock_result.scalar_one_or_none.return_value = alert
        elif n == 2:
            mock_result.first.return_value = (emb,)
        elif n == 3:
            mock_result.all.return_value = similar_rows
        elif n == 4:
            mock_result.all.return_value = execution_rows
        elif n == 5:
            # Prior query
            mock_result.all.return_value = prior_rows
        else:
            mock_result.all.return_value = []
        return mock_result

    db.execute = _execute

    score = await svc.calculate(alert_id, runbook_id)

    assert score.similar_count == 2
    # Blended: prior=0.7 (60%) + computed (40%) → well above 50
    assert 40.0 <= score.score <= 100.0
    assert score.confidence_level in ("medium", "high")


# ---------------------------------------------------------------------------
# TC-CONF-SVC-04  No embedding on alert → neutral score, insufficient_data
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_embedding_returns_insufficient_data():
    """TC-CONF-SVC-04: Alert has no embedding → score=50, confidence_level='insufficient_data'."""
    from app.services.confidence_score_service import ConfidenceScoreService

    alert_id = uuid.uuid4()
    runbook_id = uuid.uuid4()

    db = AsyncMock()
    svc = ConfidenceScoreService(db)

    alert = _make_alert(has_embedding=False)
    alert.id = alert_id

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = alert
    db.execute = AsyncMock(return_value=mock_result)

    score = await svc.calculate(alert_id, runbook_id)

    assert score.score == 50.0
    assert score.confidence_level == "insufficient_data"
    assert score.similar_count == 0


# ---------------------------------------------------------------------------
# TC-CONF-SVC-05  No execution history → score from prior only
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_execution_history_uses_prior():
    """TC-CONF-SVC-05: Similar alerts found but no executions → uses effectiveness prior."""
    from app.services.confidence_score_service import ConfidenceScoreService

    alert_id = uuid.uuid4()
    runbook_id = uuid.uuid4()

    similar_ids = [uuid.uuid4() for _ in range(5)]
    similar_rows = [_make_similar_row(aid, 0.8) for aid in similar_ids]

    # Prior: 60% success rate
    prior_rows = [MagicMock() for _ in range(10)]
    for i, r in enumerate(prior_rows):
        r.resolution_type = "full" if i < 6 else "no_effect"

    db = AsyncMock()
    svc = ConfidenceScoreService(db)

    alert = _make_alert(has_embedding=True)
    alert.id = alert_id
    emb = MagicMock()
    alert.embedding = emb

    call_count = [0]

    async def _execute(query):
        call_count[0] += 1
        n = call_count[0]
        mock_result = MagicMock()
        if n == 1:
            mock_result.scalar_one_or_none.return_value = alert
        elif n == 2:
            mock_result.first.return_value = (emb,)
        elif n == 3:
            mock_result.all.return_value = similar_rows
        elif n == 4:
            # No executions matched
            mock_result.all.return_value = []
        elif n == 5:
            # Prior query
            mock_result.all.return_value = prior_rows
        else:
            mock_result.all.return_value = []
        return mock_result

    db.execute = _execute

    score = await svc.calculate(alert_id, runbook_id)

    assert 55.0 <= score.score <= 65.0
    assert score.similar_count == 5
    assert "Limited history" in score.explanation or "overall runbook performance" in score.explanation


# ---------------------------------------------------------------------------
# TC-CONF-SVC-06  Partial outcomes count as 0.5 weight
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_partial_outcomes_half_weight():
    """TC-CONF-SVC-06: Partial resolutions contribute 0.5 to weighted score."""
    from app.services.confidence_score_service import ConfidenceScoreService

    alert_id = uuid.uuid4()
    runbook_id = uuid.uuid4()

    similar_ids = [uuid.uuid4() for _ in range(4)]
    similar_rows = [_make_similar_row(aid, 1.0) for aid in similar_ids]  # similarity=1.0 for clean math

    # 2 success, 2 partial
    execution_rows = [
        _make_execution_row(similar_ids[0], "full"),
        _make_execution_row(similar_ids[1], "full"),
        _make_execution_row(similar_ids[2], "partial"),
        _make_execution_row(similar_ids[3], "partial"),
    ]

    db = AsyncMock()
    svc = ConfidenceScoreService(db)

    alert = _make_alert(has_embedding=True)
    alert.id = alert_id
    emb = MagicMock()
    alert.embedding = emb

    call_count = [0]

    async def _execute(query):
        call_count[0] += 1
        n = call_count[0]
        mock_result = MagicMock()
        if n == 1:
            mock_result.scalar_one_or_none.return_value = alert
        elif n == 2:
            mock_result.first.return_value = (emb,)
        elif n == 3:
            mock_result.all.return_value = similar_rows
        elif n == 4:
            mock_result.all.return_value = execution_rows
        else:
            mock_result.all.return_value = []
        return mock_result

    db.execute = _execute

    score = await svc.calculate(alert_id, runbook_id)

    # weighted_successes = 2*1.0 + 2*0.5 = 3.0; weighted_total = 4.0 → raw = 0.75
    assert abs(score.score - 75.0) < 5  # Allow blending tolerance
    assert score.success_rate <= 1.0


# ---------------------------------------------------------------------------
# TC-CONF-SVC-07  bulk_calculate returns dict keyed by runbook_id
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bulk_calculate_returns_dict():
    """TC-CONF-SVC-07: bulk_calculate returns a dict keyed by each runbook_id."""
    from app.services.confidence_score_service import ConfidenceScoreService

    alert_id = uuid.uuid4()
    runbook_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

    db = AsyncMock()
    svc = ConfidenceScoreService(db)

    # Patch calculate to return a simple score
    dummy_score = ConfidenceScore(
        score=50.0,
        explanation="No data",
        similar_count=0,
        success_rate=0.0,
        confidence_level="insufficient_data",
    )

    async def _mock_calculate(a_id, r_id):
        return dummy_score

    svc.calculate = _mock_calculate

    result = await svc.bulk_calculate(alert_id, runbook_ids)

    assert set(result.keys()) == set(runbook_ids)
    for r_id in runbook_ids:
        assert isinstance(result[r_id], ConfidenceScore)


# ---------------------------------------------------------------------------
# TC-CONF-SVC-08  Alert not found → neutral score, insufficient_data
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_alert_not_found_returns_insufficient_data():
    """TC-CONF-SVC-08: Alert does not exist in DB → score=50, confidence_level='insufficient_data'."""
    from app.services.confidence_score_service import ConfidenceScoreService

    alert_id = uuid.uuid4()
    runbook_id = uuid.uuid4()

    db = AsyncMock()
    svc = ConfidenceScoreService(db)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # Not found
    db.execute = AsyncMock(return_value=mock_result)

    score = await svc.calculate(alert_id, runbook_id)

    assert score.score == 50.0
    assert score.confidence_level == "insufficient_data"
    assert score.similar_count == 0
