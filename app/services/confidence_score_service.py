"""
Confidence Score Service
Computes a 0-100% confidence score for executing a runbook on a given alert,
based on historical similarity and execution outcomes.
"""
import logging
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert
from app.models_learning import ExecutionOutcome
from app.models_remediation import RunbookExecution
from app.schemas_confidence import ConfidenceScore, SampleOutcome

logger = logging.getLogger(__name__)

# Minimum similar alerts required before we rely on computed score alone.
_BLEND_THRESHOLD = 3


def _confidence_level(score: float) -> str:
    """Map a 0–100 score to a human-readable confidence level."""
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


class ConfidenceScoreService:
    """
    Service for computing pre-execution confidence scores.

    Uses vector-similarity history (via SimilarityService) and runbook
    effectiveness data (via EffectivenessService) to produce an
    interpretable 0–100 score before an operator commits to running a
    runbook.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def calculate(
        self,
        alert_id: UUID,
        runbook_id: UUID,
    ) -> ConfidenceScore:
        """
        Calculate confidence score for running *runbook_id* on *alert_id*.

        Args:
            alert_id: UUID of the incoming alert.
            runbook_id: UUID of the candidate runbook.

        Returns:
            ConfidenceScore with score, explanation and supporting data.
        """
        # 1. Load alert – check embedding
        result = await self.db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert: Optional[Alert] = result.scalar_one_or_none()

        if alert is None or alert.embedding is None:
            logger.warning(
                "Alert %s not found or has no embedding – returning neutral score",
                alert_id,
            )
            return ConfidenceScore(
                score=50.0,
                explanation="No historical data available for this runbook. Score based on runbook configuration only.",
                similar_count=0,
                success_rate=0.0,
                avg_resolution_minutes=None,
                sample_outcomes=[],
                confidence_level="insufficient_data",
            )

        # 2. Find similar historical alerts (sync SimilarityService wrapped in run_sync)
        similar_incidents = await self._find_similar(alert_id)

        if not similar_incidents:
            # No similar history – try effectiveness prior
            return await self._score_from_prior_only(runbook_id)

        # 3. Match executions of this runbook on the similar alerts
        sample_outcomes = await self._fetch_outcomes(runbook_id, similar_incidents)

        # 4. Compute weighted score
        weighted_successes = 0.0
        weighted_total = 0.0
        resolution_times: List[float] = []

        for so in sample_outcomes:
            w = so.similarity
            weighted_total += w
            if so.outcome == "success":
                weighted_successes += w * 1.0
            elif so.outcome == "partial":
                weighted_successes += w * 0.5
            # "failure" contributes 0
            if so.resolution_time_minutes is not None:
                resolution_times.append(so.resolution_time_minutes)

        similar_count = len(similar_incidents)

        if weighted_total == 0.0:
            # Similar alerts found but none were handled by this runbook
            return await self._score_from_prior_only(runbook_id, similar_count=similar_count)

        raw_score = weighted_successes / weighted_total  # 0.0 – 1.0
        success_rate = raw_score

        # 5. Blend with prior when data is sparse
        if similar_count < _BLEND_THRESHOLD:
            prior = await self._get_prior(runbook_id)
            if prior is not None:
                raw_score = 0.6 * prior + 0.4 * raw_score
            # else: no prior, use computed as-is

        final_score = max(0.0, min(100.0, raw_score * 100))
        avg_resolution = (
            sum(resolution_times) / len(resolution_times) if resolution_times else None
        )

        # 6. Build explanation
        explanation = self._build_explanation(
            similar_count=similar_count,
            success_rate=success_rate,
            avg_resolution_minutes=avg_resolution,
            used_prior=similar_count < _BLEND_THRESHOLD,
        )

        return ConfidenceScore(
            score=round(final_score, 2),
            explanation=explanation,
            similar_count=similar_count,
            success_rate=round(success_rate, 4),
            avg_resolution_minutes=(
                round(avg_resolution, 2) if avg_resolution is not None else None
            ),
            sample_outcomes=sample_outcomes,
            confidence_level=_confidence_level(final_score),
        )

    async def bulk_calculate(
        self,
        alert_id: UUID,
        runbook_ids: List[UUID],
    ) -> Dict[UUID, ConfidenceScore]:
        """
        Calculate confidence scores for multiple runbooks against one alert.

        Args:
            alert_id: UUID of the incoming alert.
            runbook_ids: List of candidate runbook UUIDs.

        Returns:
            Dict mapping runbook_id → ConfidenceScore.
        """
        scores: Dict[UUID, ConfidenceScore] = {}
        for runbook_id in runbook_ids:
            scores[runbook_id] = await self.calculate(alert_id, runbook_id)
        return scores

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _find_similar(
        self,
        alert_id: UUID,
        limit: int = 20,
        min_similarity: float = 0.7,
    ) -> List[SampleOutcome]:
        """
        Return lightweight SampleOutcome stubs (no outcome yet) for each
        similar historical alert.  Outcome is filled in later by
        _fetch_outcomes().
        """
        from sqlalchemy.sql.expression import func as sqlfunc

        # Retrieve the embedding for the target alert
        emb_result = await self.db.execute(
            select(Alert.embedding).where(Alert.id == alert_id)
        )
        row = emb_result.first()
        if row is None or row[0] is None:
            return []

        embedding = row[0]

        # pgvector cosine distance (<=>); lower = more similar
        max_distance = 1.0 - min_similarity

        similar_result = await self.db.execute(
            select(
                Alert.id,
                (1 - Alert.embedding.cosine_distance(embedding)).label("similarity"),
            )
            .where(
                and_(
                    Alert.id != alert_id,
                    Alert.embedding.isnot(None),
                    Alert.embedding.cosine_distance(embedding) <= max_distance,
                )
            )
            .order_by(Alert.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        rows = similar_result.all()

        return [
            SampleOutcome(
                alert_id=r.id,
                similarity=float(r.similarity),
                outcome="unknown",  # will be resolved in _fetch_outcomes
                resolution_time_minutes=None,
            )
            for r in rows
        ]

    async def _fetch_outcomes(
        self,
        runbook_id: UUID,
        stubs: List[SampleOutcome],
    ) -> List[SampleOutcome]:
        """
        For each stub alert, look up the RunbookExecution + ExecutionOutcome
        for *runbook_id* and map to a canonical outcome string.
        """
        if not stubs:
            return []

        alert_ids = [s.alert_id for s in stubs]
        similarity_map = {s.alert_id: s.similarity for s in stubs}

        rows_result = await self.db.execute(
            select(
                RunbookExecution.alert_id,
                ExecutionOutcome.resolution_type,
                ExecutionOutcome.time_to_resolution_minutes,
            )
            .join(
                ExecutionOutcome,
                ExecutionOutcome.execution_id == RunbookExecution.id,
            )
            .where(
                and_(
                    RunbookExecution.runbook_id == runbook_id,
                    RunbookExecution.alert_id.in_(alert_ids),
                )
            )
        )
        rows = rows_result.all()

        # Build a map alert_id → best outcome (prefer "full" > "partial" > others)
        outcome_map: Dict[UUID, SampleOutcome] = {}
        for row in rows:
            aid = row.alert_id
            outcome_str = self._map_resolution_type(row.resolution_type)
            existing = outcome_map.get(aid)
            if existing is None or self._outcome_rank(outcome_str) > self._outcome_rank(
                existing.outcome
            ):
                outcome_map[aid] = SampleOutcome(
                    alert_id=aid,
                    similarity=similarity_map.get(aid, 0.0),
                    outcome=outcome_str,
                    resolution_time_minutes=(
                        float(row.time_to_resolution_minutes)
                        if row.time_to_resolution_minutes is not None
                        else None
                    ),
                )

        return list(outcome_map.values())

    @staticmethod
    def _map_resolution_type(resolution_type: Optional[str]) -> str:
        """Map ExecutionOutcome.resolution_type to simplified outcome string."""
        if resolution_type == "full":
            return "success"
        if resolution_type == "partial":
            return "partial"
        return "failure"

    @staticmethod
    def _outcome_rank(outcome: str) -> int:
        return {"success": 2, "partial": 1, "failure": 0, "unknown": -1}.get(outcome, -1)

    async def _get_prior(self, runbook_id: UUID) -> Optional[float]:
        """
        Retrieve overall effectiveness score (0.0–1.0) from EffectivenessService
        as a Bayesian prior.
        """
        try:
            from app.services.effectiveness_service import EffectivenessService
            from app.database import async_session_factory

            # EffectivenessService uses a sync Session; create one via the factory
            async with async_session_factory() as sync_wrapper:
                # We need a sync session — fall back to direct query here
                pass

            # Direct async approach: replicate the success_rate calculation
            result = await self.db.execute(
                select(
                    ExecutionOutcome.resolution_type,
                )
                .join(
                    RunbookExecution,
                    ExecutionOutcome.execution_id == RunbookExecution.id,
                )
                .where(RunbookExecution.runbook_id == runbook_id)
            )
            rows = result.all()

            if not rows:
                return None

            successes = sum(
                1 for r in rows if r.resolution_type == "full"
            )
            return successes / len(rows)
        except Exception as exc:
            logger.warning("Could not compute prior for runbook %s: %s", runbook_id, exc)
            return None

    async def _score_from_prior_only(
        self,
        runbook_id: UUID,
        similar_count: int = 0,
    ) -> ConfidenceScore:
        """Return a score derived purely from overall runbook effectiveness."""
        prior = await self._get_prior(runbook_id)

        if prior is None:
            return ConfidenceScore(
                score=50.0,
                explanation=(
                    "No historical data available for this runbook. "
                    "Score based on runbook configuration only."
                ),
                similar_count=similar_count,
                success_rate=0.0,
                avg_resolution_minutes=None,
                sample_outcomes=[],
                confidence_level="insufficient_data",
            )

        final_score = max(0.0, min(100.0, prior * 100))
        overall_pct = round(prior * 100, 1)
        explanation = (
            f"Limited history ({similar_count} similar incidents). "
            f"Based mainly on overall runbook performance: {overall_pct}% success rate"
        )
        return ConfidenceScore(
            score=round(final_score, 2),
            explanation=explanation,
            similar_count=similar_count,
            success_rate=round(prior, 4),
            avg_resolution_minutes=None,
            sample_outcomes=[],
            confidence_level=_confidence_level(final_score),
        )

    @staticmethod
    def _build_explanation(
        *,
        similar_count: int,
        success_rate: float,
        avg_resolution_minutes: Optional[float],
        used_prior: bool,
    ) -> str:
        """Build a plain-English explanation string."""
        pct = round(success_rate * 100, 1)

        if not used_prior:
            if avg_resolution_minutes is not None:
                t = round(avg_resolution_minutes, 1)
                return (
                    f"Based on {similar_count} similar incidents: "
                    f"{pct}% success rate, avg resolution {t} min"
                )
            return (
                f"Based on {similar_count} similar incidents: "
                f"{pct}% success rate"
            )

        return (
            f"Limited history ({similar_count} similar incidents). "
            f"Based mainly on overall runbook performance: {pct}% success rate"
        )
