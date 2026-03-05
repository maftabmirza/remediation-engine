"""
Unit tests for ConfidenceScoreService.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.schemas_confidence import ConfidenceScore, SampleOutcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_alert(has_embedding: bool = True):
    """Create a mock Alert ORM object."""
    alert = MagicMock()
    alert.id = uuid4()
    alert.embedding = b"\x00" * 128 if has_embedding else None
    return alert


def _make_runbook():
    runbook = MagicMock()
    runbook.id = uuid4()
    runbook.name = "Restart Apache"
    return runbook


def _make_execution_outcome(resolution_type: str, time_minutes=None):
    outcome = MagicMock()
    outcome.resolution_type = resolution_type
    outcome.time_to_resolution_minutes = time_minutes
    return outcome


# ---------------------------------------------------------------------------
# Import service lazily so tests don't fail if pgvector isn't installed
# ---------------------------------------------------------------------------

@pytest.fixture
def service():
    """Return a ConfidenceScoreService with an AsyncMock db session."""
    from app.services.confidence_score_service import ConfidenceScoreService

    db = AsyncMock()
    return ConfidenceScoreService(db)


# ---------------------------------------------------------------------------
# Test: no embedding → insufficient_data
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_embedding_returns_neutral_score(service):
    """Alert with no embedding returns score=50 and confidence_level='insufficient_data'."""
    alert = _make_alert(has_embedding=False)
    runbook = _make_runbook()

    # DB returns alert without embedding
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = alert
    service.db.execute = AsyncMock(return_value=mock_result)

    score = await service.calculate(alert.id, runbook.id)

    assert score.confidence_level == "insufficient_data"
    assert score.score == 50.0
    assert score.similar_count == 0


# ---------------------------------------------------------------------------
# Test: no similar alerts → falls back to prior
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_similar_alerts_uses_effectiveness_prior(service):
    """No similar alerts found → score comes from effectiveness prior."""
    alert = _make_alert(has_embedding=True)
    runbook = _make_runbook()

    # First execute call returns the alert
    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = alert

    # Second execute call (find_similar_alerts) returns empty list
    similar_result = MagicMock()
    similar_result.fetchall.return_value = []

    service.db.execute = AsyncMock(side_effect=[alert_result, similar_result])

    # Mock effectiveness prior = 65%
    with patch.object(
        service, "_get_overall_effectiveness_score", new_callable=AsyncMock, return_value=65.0
    ):
        score = await service.calculate(alert.id, runbook.id)

    assert score.similar_count == 0
    assert score.score == 65.0
    assert score.confidence_level == "medium"
    assert "65.0%" in score.explanation


# ---------------------------------------------------------------------------
# Test: high confidence — many similar alerts, high success rate
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_high_confidence_many_similar_alerts(service):
    """
    5 similar alerts all with 'full' (success) outcomes → score ≥ 70.
    """
    alert = _make_alert(has_embedding=True)
    runbook = _make_runbook()
    similar_ids = [uuid4() for _ in range(5)]
    similarity_value = 0.9

    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = alert

    similar_rows = [MagicMock(id=sid, similarity=similarity_value) for sid in similar_ids]
    similar_result = MagicMock()
    similar_result.fetchall.return_value = similar_rows

    # Each similar alert has one 'full' outcome (success), 30 min resolution
    outcome_rows = [MagicMock(resolution_type="full", time_to_resolution_minutes=30)]
    outcome_result = MagicMock()
    outcome_result.fetchall.return_value = outcome_rows

    # db.execute sequence: alert lookup, similar alerts, then 5× outcome queries
    service.db.execute = AsyncMock(
        side_effect=[alert_result, similar_result] + [outcome_result] * 5
    )

    score = await service.calculate(alert.id, runbook.id)

    assert score.score >= 70.0
    assert score.confidence_level == "high"
    assert score.similar_count == 5
    assert score.success_rate == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# Test: low confidence — many similar alerts, mostly failures
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_low_confidence_mostly_failures(service):
    """5 similar alerts all failed → score < 40."""
    alert = _make_alert(has_embedding=True)
    runbook = _make_runbook()
    similar_ids = [uuid4() for _ in range(5)]

    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = alert

    similar_rows = [MagicMock(id=sid, similarity=0.85) for sid in similar_ids]
    similar_result = MagicMock()
    similar_result.fetchall.return_value = similar_rows

    failure_rows = [MagicMock(resolution_type="no_effect", time_to_resolution_minutes=None)]
    failure_result = MagicMock()
    failure_result.fetchall.return_value = failure_rows

    service.db.execute = AsyncMock(
        side_effect=[alert_result, similar_result] + [failure_result] * 5
    )

    score = await service.calculate(alert.id, runbook.id)

    assert score.score < 40.0
    assert score.confidence_level == "low"
    assert score.success_rate == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# Test: partial outcomes count as 0.5
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_partial_outcomes_weighted_half(service):
    """Partial outcomes contribute 0.5 weight to the score."""
    alert = _make_alert(has_embedding=True)
    runbook = _make_runbook()
    similar_ids = [uuid4() for _ in range(4)]

    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = alert

    similar_rows = [MagicMock(id=sid, similarity=1.0) for sid in similar_ids]
    similar_result = MagicMock()
    similar_result.fetchall.return_value = similar_rows

    # All 4 outcomes are partial → raw_score = 0.5
    partial_rows = [MagicMock(resolution_type="partial", time_to_resolution_minutes=None)]
    partial_result = MagicMock()
    partial_result.fetchall.return_value = partial_rows

    service.db.execute = AsyncMock(
        side_effect=[alert_result, similar_result] + [partial_result] * 4
    )

    score = await service.calculate(alert.id, runbook.id)

    # 4 similar but < _BLEND_THRESHOLD=3? No, 4 >= 3, so no blend.
    # raw_score = (4 * 1.0 * 0.5) / (4 * 1.0) = 0.5 → 50.0
    assert score.success_rate == pytest.approx(0.5, abs=0.01)
    assert score.score == pytest.approx(50.0, abs=1.0)
    assert score.confidence_level == "medium"


# ---------------------------------------------------------------------------
# Test: insufficient data (<3 similar) blends with prior
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_insufficient_data_blends_with_prior(service):
    """Only 1 similar alert → blends with effectiveness prior."""
    alert = _make_alert(has_embedding=True)
    runbook = _make_runbook()
    similar_id = uuid4()

    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = alert

    similar_rows = [MagicMock(id=similar_id, similarity=0.8)]
    similar_result = MagicMock()
    similar_result.fetchall.return_value = similar_rows

    # 1 successful outcome
    outcome_rows = [MagicMock(resolution_type="full", time_to_resolution_minutes=20)]
    outcome_result = MagicMock()
    outcome_result.fetchall.return_value = outcome_rows

    service.db.execute = AsyncMock(side_effect=[alert_result, similar_result, outcome_result])

    # Prior = 80%
    with patch.object(
        service, "_get_overall_effectiveness_score", new_callable=AsyncMock, return_value=80.0
    ):
        score = await service.calculate(alert.id, runbook.id)

    assert score.similar_count == 1
    # score should be blended: 0.6*0.8 + 0.4*1.0 = 0.88 → 88.0
    assert score.score == pytest.approx(88.0, abs=1.0)
    assert score.confidence_level == "high"
    assert "Limited history" in score.explanation


# ---------------------------------------------------------------------------
# Test: no execution history at all
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_execution_history_uses_prior(service):
    """Similar alerts found but no executions → falls back to prior."""
    alert = _make_alert(has_embedding=True)
    runbook = _make_runbook()
    similar_id = uuid4()

    alert_result = MagicMock()
    alert_result.scalar_one_or_none.return_value = alert

    similar_rows = [MagicMock(id=similar_id, similarity=0.9)]
    similar_result = MagicMock()
    similar_result.fetchall.return_value = similar_rows

    # No outcomes for this runbook
    empty_outcome_result = MagicMock()
    empty_outcome_result.fetchall.return_value = []

    service.db.execute = AsyncMock(
        side_effect=[alert_result, similar_result, empty_outcome_result]
    )

    with patch.object(
        service, "_get_overall_effectiveness_score", new_callable=AsyncMock, return_value=55.0
    ):
        score = await service.calculate(alert.id, runbook.id)

    assert score.score == pytest.approx(55.0, abs=0.1)
    assert "55.0%" in score.explanation


# ---------------------------------------------------------------------------
# Test: bulk_calculate returns dict keyed by runbook_id
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_bulk_calculate_returns_dict_keyed_by_runbook_id(service):
    """bulk_calculate returns a dict mapping runbook_id → ConfidenceScore."""
    alert_id = uuid4()
    runbook_ids = [uuid4(), uuid4(), uuid4()]

    # Mock calculate to return deterministic scores
    async def _mock_calculate(a_id, r_id):
        return ConfidenceScore(
            score=75.0,
            explanation="mocked",
            similar_count=5,
            success_rate=0.75,
            sample_outcomes=[],
            confidence_level="high",
        )

    with patch.object(service, "calculate", side_effect=_mock_calculate):
        result = await service.bulk_calculate(alert_id, runbook_ids)

    assert set(result.keys()) == set(runbook_ids)
    for rid in runbook_ids:
        assert isinstance(result[rid], ConfidenceScore)
        assert result[rid].score == 75.0
