"""
Incident Service

Assembles native incident aggregates from existing alert correlations /
clusters and collects all evidence needed for postmortem generation.

Two main responsibilities:
  1. Incident assembly — materialise an Incident row from a correlation
     (primary) or cluster (fallback), optionally linking an ITSM event.
  2. Evidence collection — gather the full evidence bundle for a resolved
     incident so the postmortem service can drive LLM generation.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Alert, AlertCluster, IncidentMetrics, SolutionOutcome
from app.models_agent import AgentSession, AgentStep
from app.models_incident import Incident, RESOLUTION_GRACE_PERIOD_MINUTES
from app.models_itsm import ChangeEvent, IncidentEvent
from app.models_learning import AnalysisFeedback, ExecutionOutcome
from app.models_postmortem import PostmortemReport
from app.models_remediation import RunbookExecution, StepExecution
from app.models_troubleshooting import AlertCorrelation

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IncidentService:
    """
    Service for assembling and managing native incident aggregates.

    Typical lifecycle:
        1. ``assemble_from_correlation(correlation_id)`` or
           ``assemble_from_cluster(cluster_id)`` — create/upsert Incident.
        2. ``mark_resolved(incident_id)`` — set resolved_at + grace period.
        3. ``check_and_mark_eligible(incident_id)`` — flip eligible flag once
           grace period has elapsed.
        4. ``list_eligible_for_postmortem(...)`` — used by the API to display
           the resolved-incident picker in the UI.
        5. ``get_evidence(incident_id)`` — gather full evidence bundle for
           postmortem generation.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Incident assembly
    # ------------------------------------------------------------------

    async def assemble_from_correlation(
        self, correlation_id: UUID
    ) -> Incident:
        """
        Create or update an Incident from an AlertCorrelation.

        If an Incident already exists for this correlation it is returned
        unchanged (idempotent).

        Args:
            correlation_id: UUID of the AlertCorrelation to use as seed.

        Returns:
            The created or existing Incident.

        Raises:
            HTTPException 404 if the correlation does not exist.
        """
        # Load correlation
        corr_result = await self.db.execute(
            select(AlertCorrelation)
            .options(selectinload(AlertCorrelation.alerts))
            .where(AlertCorrelation.id == correlation_id)
        )
        correlation = corr_result.scalar_one_or_none()
        if correlation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AlertCorrelation {correlation_id} not found",
            )

        # Idempotency — return existing incident if already created
        existing = await self._find_incident_for_correlation(correlation_id)
        if existing is not None:
            return existing

        # Derive start time from the earliest alert in the correlation
        started_at = _utc_now()
        alerts = list(correlation.alerts or [])
        if alerts:
            timestamps = [
                a.timestamp for a in alerts if a.timestamp is not None
            ]
            if timestamps:
                started_at = min(timestamps)

        # Derive affected services
        affected_services = _extract_affected_services(alerts)

        # Determine status: mirror the correlation status
        inc_status = "resolved" if correlation.status == "resolved" else "open"
        resolved_at: Optional[datetime] = None
        grace_period_ends_at: Optional[datetime] = None
        is_eligible = False
        if inc_status == "resolved":
            resolved_at = correlation.updated_at or _utc_now()
            grace_period_ends_at = resolved_at + timedelta(
                minutes=RESOLUTION_GRACE_PERIOD_MINUTES
            )
            is_eligible = grace_period_ends_at <= _utc_now()

        incident = Incident(
            title=correlation.summary or f"Incident from correlation {correlation_id}",
            status=inc_status,
            severity=_highest_severity(alerts),
            correlation_id=correlation_id,
            started_at=started_at,
            resolved_at=resolved_at,
            grace_period_ends_at=grace_period_ends_at,
            is_eligible_for_postmortem=is_eligible,
            affected_services=affected_services,
        )
        self.db.add(incident)
        await self.db.commit()
        await self.db.refresh(incident)
        logger.info(
            "Assembled incident %s from correlation %s", incident.id, correlation_id
        )
        return incident

    async def assemble_from_cluster(self, cluster_id: UUID) -> Incident:
        """
        Create or update an Incident from an AlertCluster (fallback path).

        Args:
            cluster_id: UUID of the AlertCluster to use as seed.

        Returns:
            The created or existing Incident.

        Raises:
            HTTPException 404 if the cluster does not exist.
        """
        cluster_result = await self.db.execute(
            select(AlertCluster)
            .options(selectinload(AlertCluster.alerts))
            .where(AlertCluster.id == cluster_id)
        )
        cluster = cluster_result.scalar_one_or_none()
        if cluster is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AlertCluster {cluster_id} not found",
            )

        # Idempotency
        existing = await self._find_incident_for_cluster(cluster_id)
        if existing is not None:
            return existing

        alerts = list(cluster.alerts or [])
        affected_services = _extract_affected_services(alerts)

        # Closed clusters are considered resolved
        inc_status = "resolved" if not cluster.is_active else "open"
        resolved_at: Optional[datetime] = None
        grace_period_ends_at: Optional[datetime] = None
        is_eligible = False
        if inc_status == "resolved":
            resolved_at = cluster.closed_at or _utc_now()
            grace_period_ends_at = resolved_at + timedelta(
                minutes=RESOLUTION_GRACE_PERIOD_MINUTES
            )
            is_eligible = grace_period_ends_at <= _utc_now()

        incident = Incident(
            title=cluster.summary or f"Incident from cluster {cluster_id}",
            status=inc_status,
            severity=cluster.severity,
            cluster_id=cluster_id,
            started_at=cluster.first_seen or _utc_now(),
            resolved_at=resolved_at,
            grace_period_ends_at=grace_period_ends_at,
            is_eligible_for_postmortem=is_eligible,
            affected_services=affected_services,
        )
        self.db.add(incident)
        await self.db.commit()
        await self.db.refresh(incident)
        logger.info(
            "Assembled incident %s from cluster %s", incident.id, cluster_id
        )
        return incident

    async def get(self, incident_id: UUID) -> Incident:
        """Return an Incident by ID or raise 404."""
        result = await self.db.execute(
            select(Incident).where(Incident.id == incident_id)
        )
        incident = result.scalar_one_or_none()
        if incident is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident {incident_id} not found",
            )
        return incident

    async def mark_resolved(
        self,
        incident_id: UUID,
        resolved_at: Optional[datetime] = None,
    ) -> Incident:
        """
        Mark an incident as resolved and start the grace period clock.

        Args:
            incident_id: Incident to resolve.
            resolved_at: Optional explicit resolution timestamp; defaults to now.

        Returns:
            Updated Incident.
        """
        incident = await self.get(incident_id)
        resolved_at = resolved_at or _utc_now()
        incident.status = "resolved"
        incident.resolved_at = resolved_at
        incident.grace_period_ends_at = resolved_at + timedelta(
            minutes=RESOLUTION_GRACE_PERIOD_MINUTES
        )
        incident.updated_at = _utc_now()
        await self.db.commit()
        await self.db.refresh(incident)
        return incident

    async def check_and_mark_eligible(self, incident_id: UUID) -> bool:
        """
        Flip ``is_eligible_for_postmortem`` once the grace period has passed.

        Args:
            incident_id: Incident to evaluate.

        Returns:
            True if the incident is now eligible, False otherwise.
        """
        incident = await self.get(incident_id)
        if incident.is_eligible_for_postmortem:
            return True
        if (
            incident.status == "resolved"
            and incident.grace_period_ends_at is not None
            and incident.grace_period_ends_at <= _utc_now()
        ):
            incident.is_eligible_for_postmortem = True
            incident.updated_at = _utc_now()
            await self.db.commit()
            await self.db.refresh(incident)
            return True
        return False

    async def list_eligible_for_postmortem(
        self,
        page: int = 1,
        page_size: int = 20,
        include_with_postmortem: bool = False,
    ) -> tuple:
        """
        Return a paginated list of incidents eligible for postmortem generation.

        Args:
            page: Page number (1-based).
            page_size: Items per page (max 100).
            include_with_postmortem: If False (default), exclude incidents that
                already have at least one postmortem report.

        Returns:
            Tuple of (List[Incident], total_count).
        """
        query = select(Incident).where(Incident.is_eligible_for_postmortem.is_(True))

        if not include_with_postmortem:
            # Exclude incidents that already have postmortems
            subq = (
                select(PostmortemReport.incident_id)
                .where(PostmortemReport.incident_id.isnot(None))
                .scalar_subquery()
            )
            query = query.where(Incident.id.not_in(subq))

        total_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = total_result.scalar_one()

        query = (
            query.order_by(Incident.resolved_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        items = result.scalars().all()
        return items, total

    # ------------------------------------------------------------------
    # Evidence collection
    # ------------------------------------------------------------------

    async def get_evidence(self, incident_id: UUID) -> Dict[str, Any]:
        """
        Collect the full evidence bundle for a resolved incident.

        Gathers: alert timeline, runbook executions, incident metrics,
        analysis feedback, execution outcomes, agent sessions, change events,
        and similar incidents.

        Args:
            incident_id: Incident to gather evidence for.

        Returns:
            Dict with keys:
                incident, alerts, timeline, runbook_executions,
                incident_metrics, analysis_feedback, execution_outcomes,
                agent_sessions, change_events, itsm_event, affected_services,
                mttr_minutes.
        """
        incident = await self.get(incident_id)

        # 1. Collect member alerts
        alerts = await self._get_incident_alerts(incident)

        # 2. Build merged timeline
        timeline = _build_timeline(incident, alerts)

        # 3. Runbook executions + step outputs
        runbook_executions = await self._get_runbook_executions(alerts)
        for ex in runbook_executions:
            if ex.started_at:
                timeline.append(
                    {
                        "timestamp": ex.started_at.isoformat(),
                        "event": f"Runbook execution started (id={ex.id})",
                        "source": "runbook_execution",
                        "manual": False,
                    }
                )
            if ex.completed_at:
                timeline.append(
                    {
                        "timestamp": ex.completed_at.isoformat(),
                        "event": f"Runbook execution completed with status '{ex.status}'",
                        "source": "runbook_execution",
                        "manual": False,
                    }
                )

        # 4. Incident metrics (per-alert IncidentMetrics rows)
        incident_metrics = await self._get_incident_metrics(alerts)

        # 5. Analysis feedback
        analysis_feedback = await self._get_analysis_feedback(alerts)

        # 6. Execution outcomes
        execution_outcomes = await self._get_execution_outcomes(alerts)

        # 7. Agent sessions / AI troubleshooting history
        agent_sessions = await self._get_agent_sessions(alerts)

        # 8. Change events near the incident window
        change_events = await self._get_change_events(
            incident.started_at,
            incident.resolved_at or _utc_now(),
        )

        # 9. ITSM event
        itsm_event: Optional[IncidentEvent] = None
        if incident.itsm_event_id is not None:
            itsm_result = await self.db.execute(
                select(IncidentEvent).where(
                    IncidentEvent.id == incident.itsm_event_id
                )
            )
            itsm_event = itsm_result.scalar_one_or_none()

        # Sort timeline chronologically
        timeline.sort(key=lambda e: e.get("timestamp", ""))

        # Compute MTTR
        mttr_minutes: Optional[float] = None
        if incident.started_at and incident.resolved_at:
            delta = incident.resolved_at - incident.started_at
            mttr_minutes = round(delta.total_seconds() / 60, 2)

        return {
            "incident": incident,
            "alerts": alerts,
            "timeline": timeline,
            "runbook_executions": runbook_executions,
            "incident_metrics": incident_metrics,
            "analysis_feedback": analysis_feedback,
            "execution_outcomes": execution_outcomes,
            "agent_sessions": agent_sessions,
            "change_events": change_events,
            "itsm_event": itsm_event,
            "affected_services": incident.affected_services or [],
            "mttr_minutes": mttr_minutes,
        }

    # ------------------------------------------------------------------
    # Alert compatibility helper
    # ------------------------------------------------------------------

    async def find_or_create_incident_for_alert(self, alert: Alert) -> Incident:
        """
        Resolve or create an Incident for a single alert.

        Lookup order:
          1. Alert has a correlation_id → assemble from correlation.
          2. Alert has a cluster_id     → assemble from cluster.
          3. Neither                    → create a standalone incident.

        Args:
            alert: The triggering Alert.

        Returns:
            Incident for this alert.
        """
        if alert.correlation_id is not None:
            return await self.assemble_from_correlation(alert.correlation_id)

        if alert.cluster_id is not None:
            return await self.assemble_from_cluster(alert.cluster_id)

        # Standalone incident from a single alert
        existing = await self._find_incident_for_alert(alert.id)
        if existing is not None:
            return existing

        inc_status = "resolved" if alert.status == "resolved" else "open"
        resolved_at: Optional[datetime] = None
        grace_period_ends_at: Optional[datetime] = None
        is_eligible = False
        if inc_status == "resolved":
            resolved_at = _utc_now()
            grace_period_ends_at = resolved_at + timedelta(
                minutes=RESOLUTION_GRACE_PERIOD_MINUTES
            )
            is_eligible = grace_period_ends_at <= _utc_now()

        incident = Incident(
            title=f"Incident: {alert.alert_name}",
            status=inc_status,
            severity=alert.severity,
            started_at=alert.timestamp or _utc_now(),
            resolved_at=resolved_at,
            grace_period_ends_at=grace_period_ends_at,
            is_eligible_for_postmortem=is_eligible,
            affected_services=_extract_affected_services([alert]),
        )
        self.db.add(incident)
        await self.db.commit()
        await self.db.refresh(incident)
        return incident

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _find_incident_for_correlation(
        self, correlation_id: UUID
    ) -> Optional[Incident]:
        result = await self.db.execute(
            select(Incident).where(Incident.correlation_id == correlation_id)
        )
        return result.scalar_one_or_none()

    async def _find_incident_for_cluster(
        self, cluster_id: UUID
    ) -> Optional[Incident]:
        result = await self.db.execute(
            select(Incident).where(Incident.cluster_id == cluster_id)
        )
        return result.scalar_one_or_none()

    async def _find_incident_for_alert(self, alert_id: UUID) -> Optional[Incident]:
        """Find any incident whose correlation or cluster contains this alert."""
        # Join via alert's cluster/correlation FK
        alert_result = await self.db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = alert_result.scalar_one_or_none()
        if alert is None:
            return None
        if alert.correlation_id:
            return await self._find_incident_for_correlation(alert.correlation_id)
        if alert.cluster_id:
            return await self._find_incident_for_cluster(alert.cluster_id)
        return None

    async def _get_incident_alerts(self, incident: Incident) -> List[Alert]:
        """Return all alerts that belong to this incident."""
        alerts: List[Alert] = []

        if incident.correlation_id:
            result = await self.db.execute(
                select(Alert).where(Alert.correlation_id == incident.correlation_id)
            )
            alerts = list(result.scalars().all())
        elif incident.cluster_id:
            result = await self.db.execute(
                select(Alert).where(Alert.cluster_id == incident.cluster_id)
            )
            alerts = list(result.scalars().all())

        return alerts

    async def _get_runbook_executions(
        self, alerts: List[Alert]
    ) -> List[RunbookExecution]:
        if not alerts:
            return []
        alert_ids = [a.id for a in alerts]
        result = await self.db.execute(
            select(RunbookExecution)
            .options(selectinload(RunbookExecution.step_executions))
            .where(RunbookExecution.alert_id.in_(alert_ids))
            .order_by(RunbookExecution.started_at)
        )
        return list(result.scalars().all())

    async def _get_incident_metrics(
        self, alerts: List[Alert]
    ) -> List[IncidentMetrics]:
        if not alerts:
            return []
        alert_ids = [a.id for a in alerts]
        result = await self.db.execute(
            select(IncidentMetrics).where(IncidentMetrics.alert_id.in_(alert_ids))
        )
        return list(result.scalars().all())

    async def _get_analysis_feedback(
        self, alerts: List[Alert]
    ) -> List[AnalysisFeedback]:
        if not alerts:
            return []
        alert_ids = [a.id for a in alerts]
        result = await self.db.execute(
            select(AnalysisFeedback).where(AnalysisFeedback.alert_id.in_(alert_ids))
        )
        return list(result.scalars().all())

    async def _get_execution_outcomes(
        self, alerts: List[Alert]
    ) -> List[ExecutionOutcome]:
        if not alerts:
            return []
        alert_ids = [a.id for a in alerts]
        result = await self.db.execute(
            select(ExecutionOutcome).where(ExecutionOutcome.alert_id.in_(alert_ids))
        )
        return list(result.scalars().all())

    async def _get_agent_sessions(
        self, alerts: List[Alert]
    ) -> List[AgentSession]:
        if not alerts:
            return []
        alert_ids = [a.id for a in alerts]
        result = await self.db.execute(
            select(AgentSession)
            .options(selectinload(AgentSession.steps))
            .where(AgentSession.alert_id.in_(alert_ids))
            .order_by(AgentSession.started_at)
        )
        return list(result.scalars().all())

    async def _get_change_events(
        self,
        window_start: datetime,
        window_end: datetime,
        lookback_hours: int = 24,
    ) -> List[ChangeEvent]:
        """
        Return ChangeEvents that overlap with or precede the incident window.

        Looks back ``lookback_hours`` before ``window_start`` to catch
        pre-incident changes that may have contributed.
        """
        earliest = window_start - timedelta(hours=lookback_hours)
        result = await self.db.execute(
            select(ChangeEvent).where(
                and_(
                    ChangeEvent.timestamp >= earliest,
                    ChangeEvent.timestamp <= window_end,
                )
            )
            .order_by(ChangeEvent.timestamp)
        )
        return list(result.scalars().all())


# ------------------------------------------------------------------
# Module-level helpers (pure functions — no DB access)
# ------------------------------------------------------------------

def _extract_affected_services(alerts: List[Alert]) -> List[str]:
    """Deduplicate service/job names from a list of alerts."""
    seen: set = set()
    services: List[str] = []
    for alert in alerts:
        for val in (alert.job, alert.instance):
            if val and val not in seen:
                seen.add(val)
                services.append(val)
    return services


def _highest_severity(alerts: List[Alert]) -> Optional[str]:
    """Return the highest severity level across a list of alerts."""
    order = {"critical": 4, "high": 3, "warning": 2, "medium": 2, "low": 1, "info": 1}
    severities = [a.severity for a in alerts if a.severity]
    if not severities:
        return None
    return max(severities, key=lambda s: order.get(s.lower() if s else s, 0))


def _build_timeline(
    incident: Incident, alerts: List[Alert]
) -> List[Dict[str, Any]]:
    """Build an initial timeline from the incident's alert timestamps."""
    events: List[Dict[str, Any]] = []
    for alert in sorted(
        alerts, key=lambda a: a.timestamp or datetime.min.replace(tzinfo=timezone.utc)
    ):
        if alert.timestamp:
            events.append(
                {
                    "timestamp": alert.timestamp.isoformat(),
                    "event": f"Alert fired: {alert.alert_name}",
                    "source": "alert",
                    "manual": False,
                }
            )
    if incident.resolved_at:
        events.append(
            {
                "timestamp": incident.resolved_at.isoformat(),
                "event": "Incident resolved",
                "source": "incident",
                "manual": False,
            }
        )
    return events
