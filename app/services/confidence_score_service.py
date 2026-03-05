"""
Confidence Score Service

Computes a 0-100 confidence score for executing a runbook against a specific
alert, based on historical performance on semantically similar alerts.
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

# Minimum number of similar alerts before we trust the computed score alone.
_BLEND_THRESHOLD = 3

# Blending weights when similar_count < _BLEND_THRESHOLD.
_PRIOR_WEIGHT = 0.6
_COMPUTED_WEIGHT = 0.4

# Weight for each outcome type in the confidence calculation.
_OUTCOME_WEIGHTS: Dict[str, float] = {
    "success": 1.0,
    "partial": 0.5,
    "failure": 0.0,
}


def _confidence_level(score: float) -> str:
    """Map a numeric score to a named confidence level."""
    if score >= 70.0:
        return "high"
    if score >= 40.0:
        return "medium"
    return "low"


class ConfidenceScoreService:
    """
    Computes runbook confidence scores from historical execution outcomes.

    The score is weighted by the cosine similarity of each historical alert
    to the current alert, so closer matches have a larger influence.
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
        Calculate a confidence score for executing *runbook_id* on *alert_id*.

        Args:
            alert_id: UUID of the incoming alert.
            runbook_id: UUID of the candidate runbook.

        Returns:
            ConfidenceScore populated with score, explanation, and sample data.
        """
        # 1. Load alert; bail out early if no embedding.
        alert_result = await self.db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = alert_result.scalar_one_or_none()

        if alert is None or not getattr(alert, "embedding", None):
            return ConfidenceScore(
                score=50.0,
                explanation="No historical data available for this runbook. Score based on runbook configuration only.",
                similar_count=0,
                success_rate=0.0,
                avg_resolution_minutes=None,
                sample_outcomes=[],
                confidence_level="insufficient_data",
            )

        # 2. Find similar historical alerts via pgvector cosine distance.
        similar_incidents = await self._find_similar_alerts(alert, limit=20, min_similarity=0.7)

        if not similar_incidents:
            # No similar alerts → try effectiveness prior.
            return await self._score_from_prior_only(runbook_id, similar_count=0)

        # 3. Fetch execution outcomes for each similar alert + this runbook.
        sample_outcomes: List[SampleOutcome] = []
        weighted_successes: float = 0.0
        weighted_total: float = 0.0
        resolution_times: List[float] = []

        for sim_alert_id, similarity in similar_incidents:
            outcomes = await self._get_outcomes_for_alert_runbook(sim_alert_id, runbook_id)
            for outcome_type, resolution_minutes in outcomes:
                weight = _OUTCOME_WEIGHTS.get(outcome_type, 0.0)

                weighted_successes += similarity * weight
                weighted_total += similarity

                if resolution_minutes is not None:
                    resolution_times.append(resolution_minutes)

                sample_outcomes.append(
                    SampleOutcome(
                        alert_id=sim_alert_id,
                        similarity=round(similarity, 4),
                        outcome=outcome_type,
                        resolution_time_minutes=resolution_minutes,
                    )
                )

        similar_count = len({so.alert_id for so in sample_outcomes})
        avg_resolution = (
            sum(resolution_times) / len(resolution_times) if resolution_times else None
        )

        if weighted_total == 0.0:
            # Similar alerts found but none had executions → use prior.
            return await self._score_from_prior_only(runbook_id, similar_count=similar_count)

        raw_score = weighted_successes / weighted_total  # 0.0 – 1.0
        success_rate = raw_score

        # 4. Blend with effectiveness prior when data is sparse.
        if similar_count < _BLEND_THRESHOLD:
            blended_score, explanation = await self._blend_with_prior(
                runbook_id=runbook_id,
                computed_score=raw_score,
                similar_count=similar_count,
            )
            final_score = blended_score
        else:
            final_score = raw_score * 100.0
            pct = round(success_rate * 100, 1)
            t_str = (
                f", avg resolution {round(avg_resolution, 1)} min"
                if avg_resolution is not None
                else ""
            )
            explanation = (
                f"Based on {similar_count} similar incidents: "
                f"{pct}% success rate{t_str}"
            )

        return ConfidenceScore(
            score=round(final_score, 2),
            explanation=explanation,
            similar_count=similar_count,
            success_rate=round(success_rate, 4),
            avg_resolution_minutes=round(avg_resolution, 2) if avg_resolution is not None else None,
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
        results: Dict[UUID, ConfidenceScore] = {}
        for runbook_id in runbook_ids:
            results[runbook_id] = await self.calculate(alert_id, runbook_id)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _find_similar_alerts(
        self,
        alert: Alert,
        limit: int,
        min_similarity: float,
    ) -> List[tuple]:
        """
        Return (alert_id, similarity) pairs for alerts similar to *alert*.

        Uses pgvector cosine distance (<=>).  Returns an empty list if the
        embedding column is unavailable or pgvector is not installed.
        """
        try:
            from pgvector.sqlalchemy import Vector  # noqa: PLC0415

            stmt = (
                select(
                    Alert.id,
                    (1 - Alert.embedding.cosine_distance(alert.embedding)).label("similarity"),
                )
                .where(
                    and_(
                        Alert.id != alert.id,
                        Alert.embedding.isnot(None),
                        Alert.embedding.cosine_distance(alert.embedding) <= (1 - min_similarity),
                    )
                )
                .order_by(Alert.embedding.cosine_distance(alert.embedding))
                .limit(limit)
            )
            result = await self.db.execute(stmt)
            return [(row.id, float(row.similarity)) for row in result.fetchall()]
        except Exception as exc:
            logger.warning("Could not query similar alerts via pgvector: %s", exc)
            return []

    async def _get_outcomes_for_alert_runbook(
        self,
        alert_id: UUID,
        runbook_id: UUID,
    ) -> List[tuple]:
        """
        Return (outcome_type, resolution_time_minutes) for every execution of
        *runbook_id* that was triggered by *alert_id*.
        """
        stmt = (
            select(
                ExecutionOutcome.resolution_type,
                ExecutionOutcome.time_to_resolution_minutes,
            )
            .join(
                RunbookExecution,
                RunbookExecution.id == ExecutionOutcome.execution_id,
            )
            .where(
                and_(
                    RunbookExecution.alert_id == alert_id,
                    RunbookExecution.runbook_id == runbook_id,
                )
            )
        )
        result = await self.db.execute(stmt)
        rows = result.fetchall()

        outcomes = []
        for row in rows:
            resolution_type = row.resolution_type or ""
            if resolution_type == "full":
                outcome_str = "success"
            elif resolution_type == "partial":
                outcome_str = "partial"
            else:
                outcome_str = "failure"

            res_time = (
                float(row.time_to_resolution_minutes)
                if row.time_to_resolution_minutes is not None
                else None
            )
            outcomes.append((outcome_str, res_time))

        return outcomes

    async def _get_overall_effectiveness_score(
        self,
        runbook_id: UUID,
    ) -> Optional[float]:
        """
        Return the overall effectiveness score (0-100) from EffectivenessService,
        or None if insufficient data.
        """
        try:
            from app.services.effectiveness_service import EffectivenessService  # noqa: PLC0415
            from app.database import SessionLocal  # noqa: PLC0415

            # EffectivenessService uses a sync Session; run in a thread to avoid
            # blocking the event loop.
            import asyncio  # noqa: PLC0415

            def _sync_call():
                with SessionLocal() as sync_db:
                    svc = EffectivenessService(sync_db)
                    result = svc.calculate_runbook_effectiveness(runbook_id)
                    return result.overall_score if result else None

            return await asyncio.get_event_loop().run_in_executor(None, _sync_call)
        except Exception as exc:
            logger.warning("Could not retrieve effectiveness score for runbook %s: %s", runbook_id, exc)
            return None

    async def _score_from_prior_only(
        self,
        runbook_id: UUID,
        similar_count: int,
    ) -> ConfidenceScore:
        """Build a ConfidenceScore entirely from the effectiveness prior."""
        prior = await self._get_overall_effectiveness_score(runbook_id)

        if prior is not None:
            score = round(prior, 2)
            explanation = (
                f"Limited history ({similar_count} similar incidents). "
                f"Based mainly on overall runbook performance: "
                f"{round(prior, 1)}% success rate"
            )
        else:
            score = 50.0
            explanation = (
                "No historical data available for this runbook. "
                "Score based on runbook configuration only."
            )

        return ConfidenceScore(
            score=score,
            explanation=explanation,
            similar_count=similar_count,
            success_rate=round(score / 100.0, 4),
            avg_resolution_minutes=None,
            sample_outcomes=[],
            confidence_level=_confidence_level(score),
        )

    async def _blend_with_prior(
        self,
        runbook_id: UUID,
        computed_score: float,
        similar_count: int,
    ) -> tuple:
        """
        Blend *computed_score* (0-1) with the overall effectiveness prior.

        Returns (blended_score_0_100, explanation_str).
        """
        prior = await self._get_overall_effectiveness_score(runbook_id)

        if prior is not None:
            prior_normalized = prior / 100.0
            blended = (
                _PRIOR_WEIGHT * prior_normalized + _COMPUTED_WEIGHT * computed_score
            ) * 100.0
            explanation = (
                f"Limited history ({similar_count} similar incidents). "
                f"Based mainly on overall runbook performance: "
                f"{round(prior, 1)}% success rate"
            )
        else:
            blended = computed_score * 100.0
            pct = round(computed_score * 100, 1)
            explanation = (
                f"Based on {similar_count} similar incident(s): "
                f"{pct}% success rate"
            )

        return round(blended, 2), explanation
