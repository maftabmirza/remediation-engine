"""
Service Health Score & Topology Service (Feature A2).

Computes composite health scores per application/component and exposes
topology data in D3.js-compatible format.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert
from app.models_application import Application, ApplicationComponent, ComponentDependency
from app.models_itsm import ChangeEvent, ChangeImpactAnalysis
from app.models_learning import ExecutionOutcome
from app.models_remediation import RunbookExecution
from app.schemas_health import (
    HealthFactor,
    ServiceHealthScore,
    TopologyEdge,
    TopologyGraph,
    TopologyNode,
)

logger = logging.getLogger(__name__)

_SEVERITY_PENALTIES: Dict[str, float] = {
    "critical": -40.0,
    "warning": -15.0,
    "info": -5.0,
}

_STATUS_THRESHOLDS = [
    (80.0, "healthy"),
    (50.0, "degraded"),
    (0.0, "critical"),
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _score_to_status(score: float) -> str:
    """Map a numeric score to a status label."""
    for threshold, label in _STATUS_THRESHOLDS:
        if score >= threshold:
            return label
    return "critical"


class ServiceHealthService:
    """
    Service for computing application health scores and building topology graphs.

    Typical usage:
        svc = ServiceHealthService(db)
        score = await svc.calculate_health(app_id)
        topology = await svc.get_topology(app_id)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._health_cache: Dict[UUID, ServiceHealthScore] = {}
        self._computing: Set[UUID] = set()  # Guard against circular dependency recursion

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def calculate_health(self, app_id: UUID) -> ServiceHealthScore:
        """
        Compute a composite health score for *app_id*.

        Four weighted factors are considered:
          1. Active alerts (40%)
          2. Execution success rate (25%)
          3. Dependency health (20%)
          4. Change risk (15%)

        Factors with no data have their weight redistributed to the
        remaining factors proportionally.

        Args:
            app_id: UUID of the application.

        Returns:
            ServiceHealthScore with per-factor breakdown.

        Raises:
            HTTPException 404 if the application does not exist.
        """
        from fastapi import HTTPException, status as http_status  # noqa: PLC0415

        # Guard against circular dependency recursion
        if app_id in self._computing:
            return ServiceHealthScore(
                app_id=app_id,
                app_name=str(app_id),
                score=0.0,
                status="unknown",
                factors=[],
                active_alerts=0,
                critical_alerts=0,
                computed_at=_utc_now(),
            )

        self._computing.add(app_id)
        try:
            return await self._calculate_health_inner(app_id)
        finally:
            self._computing.discard(app_id)

    async def _calculate_health_inner(self, app_id: UUID) -> ServiceHealthScore:
        """Internal health computation — called only when not already computing."""
        from fastapi import HTTPException, status as http_status  # noqa: PLC0415

        # Look up application
        app_result = await self.db.execute(
            select(Application).where(Application.id == app_id)
        )
        app = app_result.scalar_one_or_none()
        if app is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Application {app_id} not found",
            )

        factors_data: List[Tuple[str, float, Optional[float], str]] = []
        # (name, default_weight, score_or_None, detail)

        # ----------------------------------------------------------------
        # Factor 1: Active Alerts (weight 40%)
        # ----------------------------------------------------------------
        alerts_result = await self.db.execute(
            select(Alert).where(
                Alert.app_id == app_id,
                Alert.status == "firing",
            )
        )
        active_alerts: List[Alert] = alerts_result.scalars().all()
        critical_count = sum(1 for a in active_alerts if a.severity == "critical")

        # Check if the application has *any* alerts ever (to determine if weight is valid)
        any_alerts_result = await self.db.execute(
            select(func.count()).where(Alert.app_id == app_id)
        )
        any_alerts_count = any_alerts_result.scalar_one()

        if any_alerts_count == 0:
            # No alert history — factor has no data
            alert_score = None
            alert_detail = "No alert history for this application"
        else:
            penalty = sum(
                _SEVERITY_PENALTIES.get(a.severity or "info", -5.0)
                for a in active_alerts
            )
            alert_score = max(0.0, 100.0 + penalty)
            active = len(active_alerts)
            alert_detail = (
                f"{active} firing alert(s): {critical_count} critical, "
                f"{active - critical_count} non-critical"
            )

        factors_data.append(("active_alerts", 0.40, alert_score, alert_detail))

        # ----------------------------------------------------------------
        # Factor 2: Execution Success Rate (weight 25%)
        # ----------------------------------------------------------------
        exec_success_score, exec_detail = await self._compute_execution_factor(app_id)
        factors_data.append(("execution_success", 0.25, exec_success_score, exec_detail))

        # ----------------------------------------------------------------
        # Factor 3: Dependency Health (weight 20%)
        # ----------------------------------------------------------------
        dep_score, dep_detail, dep_forced_critical = await self._compute_dependency_factor(
            app_id
        )
        factors_data.append(("dependency_health", 0.20, dep_score, dep_detail))

        # ----------------------------------------------------------------
        # Factor 4: Change Risk (weight 15%)
        # ----------------------------------------------------------------
        change_score, change_detail = await self._compute_change_risk_factor(app_id)
        factors_data.append(("change_risk", 0.15, change_score, change_detail))

        # ----------------------------------------------------------------
        # Weight redistribution
        # ----------------------------------------------------------------
        available = [(name, w, s, d) for name, w, s, d in factors_data if s is not None]
        if not available:
            # No data at all → unknown
            return ServiceHealthScore(
                app_id=app_id,
                app_name=app.name,
                score=0.0,
                status="unknown",
                factors=[],
                active_alerts=len(active_alerts),
                critical_alerts=critical_count,
                computed_at=_utc_now(),
            )

        total_available_weight = sum(w for _, w, _, _ in available)
        factors: List[HealthFactor] = []
        composite_score = 0.0

        for name, default_weight, score_val, detail in factors_data:
            if score_val is None:
                actual_weight = 0.0
                effective_score = 0.0
                detail = detail + " (weight redistributed)"
            else:
                actual_weight = default_weight / total_available_weight
                effective_score = float(score_val)

            factors.append(
                HealthFactor(
                    name=name,
                    weight=round(actual_weight, 4),
                    score=round(effective_score, 2),
                    detail=detail,
                )
            )
            composite_score += actual_weight * effective_score

        composite_score = round(composite_score, 2)

        # Hard-dependency override: if a hard dep forced critical, cap at 20
        if dep_forced_critical:
            composite_score = min(composite_score, 20.0)

        final_status = _score_to_status(composite_score)

        health = ServiceHealthScore(
            app_id=app_id,
            app_name=app.name,
            score=composite_score,
            status=final_status,
            factors=factors,
            active_alerts=len(active_alerts),
            critical_alerts=critical_count,
            computed_at=_utc_now(),
        )
        # Cache for topology calls
        self._health_cache[app_id] = health
        return health

    async def get_topology(
        self,
        app_id: Optional[UUID] = None,
    ) -> TopologyGraph:
        """
        Build a D3.js-compatible topology graph.

        Args:
            app_id: When provided, restrict graph to the application's
                    components and their direct dependencies.

        Returns:
            TopologyGraph with nodes and edges.
        """
        # Load components
        comp_query = select(ApplicationComponent)
        if app_id is not None:
            comp_query = comp_query.where(ApplicationComponent.app_id == app_id)

        comp_result = await self.db.execute(comp_query)
        components: List[ApplicationComponent] = comp_result.scalars().all()

        if not components:
            return TopologyGraph(nodes=[], edges=[], computed_at=_utc_now())

        component_ids = {c.id for c in components}

        # Load all dependencies involving these components
        dep_result = await self.db.execute(
            select(ComponentDependency).where(
                ComponentDependency.from_component_id.in_(component_ids)
            )
        )
        dependencies: List[ComponentDependency] = dep_result.scalars().all()

        # Collect all referenced app_ids for health computation
        app_ids_needed: Set[UUID] = {c.app_id for c in components}

        # Load application names in bulk
        apps_result = await self.db.execute(
            select(Application).where(Application.id.in_(app_ids_needed))
        )
        app_map: Dict[UUID, Application] = {
            a.id: a for a in apps_result.scalars().all()
        }

        # Compute health per app (cached)
        for aid in app_ids_needed:
            if aid not in self._health_cache:
                try:
                    await self.calculate_health(aid)
                except Exception as exc:
                    logger.warning("Could not compute health for app %s: %s", aid, exc)

        # Build nodes
        nodes: List[TopologyNode] = []
        for comp in components:
            app = app_map.get(comp.app_id)
            app_name = app.name if app else str(comp.app_id)
            health = self._health_cache.get(comp.app_id)
            nodes.append(
                TopologyNode(
                    id=str(comp.id),
                    name=comp.name,
                    type=comp.component_type or "unknown",
                    app_id=str(comp.app_id),
                    app_name=app_name,
                    health_score=health.score if health else None,
                    health_status=health.status if health else "unknown",
                    is_hard_dependency=None,
                )
            )

        # Build edges
        edges: List[TopologyEdge] = []
        for dep in dependencies:
            failure_impact_text = (dep.failure_impact or "").lower()
            if dep.dependency_type == "sync":
                impact_label = "hard"
            elif dep.dependency_type == "optional":
                impact_label = "soft"
            else:
                # Infer from failure_impact text
                impact_label = (
                    "hard" if "hard" in failure_impact_text else "soft"
                )
            edges.append(
                TopologyEdge(
                    source=str(dep.from_component_id),
                    target=str(dep.to_component_id),
                    type=dep.dependency_type or "sync",
                    failure_impact=impact_label,
                )
            )

        return TopologyGraph(
            nodes=nodes,
            edges=edges,
            computed_at=_utc_now(),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _compute_execution_factor(
        self,
        app_id: UUID,
    ) -> Tuple[Optional[float], str]:
        """
        Compute the execution success factor (0-100).

        Returns (score_or_None, detail_str).
        """
        # Recent executions for alerts linked to this app
        result = await self.db.execute(
            select(RunbookExecution)
            .join(Alert, RunbookExecution.alert_id == Alert.id)
            .where(Alert.app_id == app_id)
        )
        executions: List[RunbookExecution] = result.scalars().all()

        if not executions:
            return None, "No runbook executions for this application"

        success_count = sum(1 for e in executions if e.status == "success")
        rate = success_count / len(executions)
        score = round(rate * 100.0, 2)
        detail = (
            f"{success_count}/{len(executions)} executions successful "
            f"({score:.1f}%)"
        )
        return score, detail

    async def _compute_dependency_factor(
        self,
        app_id: UUID,
    ) -> Tuple[Optional[float], str, bool]:
        """
        Compute the dependency health factor using BFS with cycle detection.

        Returns (score_or_None, detail_str, forced_critical).
        forced_critical is True when a hard dependency has score < 30.
        """
        # Get components for this app
        comp_result = await self.db.execute(
            select(ApplicationComponent).where(ApplicationComponent.app_id == app_id)
        )
        my_components: List[ApplicationComponent] = comp_result.scalars().all()

        if not my_components:
            return None, "No components defined for this application", False

        my_comp_ids = {c.id for c in my_components}

        # Get direct dependencies (outgoing edges from app's components)
        dep_result = await self.db.execute(
            select(ComponentDependency).where(
                ComponentDependency.from_component_id.in_(my_comp_ids)
            )
        )
        direct_deps: List[ComponentDependency] = dep_result.scalars().all()

        if not direct_deps:
            return None, "No dependencies defined for this application", False

        # BFS traversal with cycle detection
        visited: Set[UUID] = set(my_comp_ids)
        queue: List[Tuple[ComponentDependency, bool]] = [
            (d, d.dependency_type == "sync") for d in direct_deps
        ]

        dep_app_scores: List[Tuple[float, bool]] = []  # (score, is_hard)
        forced_critical = False

        # Collect all unique dep app IDs via BFS
        dep_app_ids: Dict[UUID, bool] = {}  # app_id -> is_hard

        while queue:
            dep, is_hard = queue.pop(0)
            target_id = dep.to_component_id

            if target_id in visited:
                continue
            visited.add(target_id)

            # Get the application of the target component
            target_result = await self.db.execute(
                select(ApplicationComponent).where(
                    ApplicationComponent.id == target_id
                )
            )
            target_comp = target_result.scalar_one_or_none()
            if target_comp is None:
                continue

            tid = target_comp.app_id
            if tid not in dep_app_ids:
                dep_app_ids[tid] = is_hard
            elif is_hard:
                dep_app_ids[tid] = True  # hard overrides soft

            # Continue BFS through target's outgoing deps
            next_deps_result = await self.db.execute(
                select(ComponentDependency).where(
                    ComponentDependency.from_component_id == target_id
                )
            )
            for nd in next_deps_result.scalars().all():
                queue.append((nd, nd.dependency_type == "sync"))

        if not dep_app_ids:
            return None, "No reachable dependency apps", False

        # Compute or retrieve health for each dependency app
        scores: List[float] = []
        for dep_app_id, is_hard in dep_app_ids.items():
            if dep_app_id == app_id:
                continue
            if dep_app_id in self._health_cache:
                dep_health = self._health_cache[dep_app_id]
            else:
                try:
                    dep_health = await self.calculate_health(dep_app_id)
                except Exception:
                    continue

            dep_score = dep_health.score
            scores.append(dep_score)

            if is_hard and dep_score < 30.0:
                forced_critical = True
            elif not is_hard and dep_score < 50.0:
                dep_score = dep_score * 0.85  # reduce by 15%

            dep_app_scores.append((dep_score, is_hard))

        if not dep_app_scores:
            return None, "No dependency health data available", False

        avg_score = round(sum(s for s, _ in dep_app_scores) / len(dep_app_scores), 2)
        detail = (
            f"Avg dependency health: {avg_score:.1f} across "
            f"{len(dep_app_scores)} dependency app(s)"
        )
        if forced_critical:
            detail += " — HARD dependency in critical state"

        return avg_score, detail, forced_critical

    async def _compute_change_risk_factor(
        self,
        app_id: UUID,
    ) -> Tuple[Optional[float], str]:
        """
        Compute the change-risk factor based on recent ChangeImpactAnalysis records.

        Returns (score_or_None, detail_str).
        """
        # Get application name for matching change events
        app_result = await self.db.execute(
            select(Application).where(Application.id == app_id)
        )
        app = app_result.scalar_one_or_none()
        if app is None:
            return None, "Application not found"

        # Find recent ChangeImpactAnalysis records for this app's service name
        impact_result = await self.db.execute(
            select(ChangeImpactAnalysis)
            .join(ChangeEvent, ChangeImpactAnalysis.change_event_id == ChangeEvent.id)
            .where(ChangeEvent.application == app.name)
        )
        impact_records: List[ChangeImpactAnalysis] = impact_result.scalars().all()

        if not impact_records:
            return None, "No recent change impact data for this application"

        avg_correlation = sum(
            r.correlation_score for r in impact_records
        ) / len(impact_records)

        score = round(max(0.0, 100.0 - avg_correlation * 100.0), 2)
        detail = (
            f"Avg change correlation: {avg_correlation:.2f} from "
            f"{len(impact_records)} recent change(s). Risk score: {score:.1f}"
        )
        return score, detail
