"""
Service Health Score & Topology Service (Feature A2)

Computes composite health scores per application/component and exposes
topology data for D3.js visualisation.  Gives operators an instant
"is my service healthy?" view with dependency-aware degradation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_application import Application, ApplicationComponent, ComponentDependency
from app.schemas_health import (
    HealthFactor,
    ServiceHealthScore,
    TopologyEdge,
    TopologyGraph,
    TopologyNode,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Status thresholds
# ---------------------------------------------------------------------------

def _score_to_status(score: float) -> str:
    if score >= 80:
        return "healthy"
    if score >= 50:
        return "degraded"
    return "critical"


# ---------------------------------------------------------------------------
# Factor names (constants for consistency)
# ---------------------------------------------------------------------------

FACTOR_ALERTS = "active_alerts"
FACTOR_EXECUTION = "execution_success"
FACTOR_DEPENDENCY = "dependency_health"
FACTOR_CHANGE = "change_risk"


class ServiceHealthService:
    """
    Service that computes composite health scores and topology graphs.

    All public methods are async-first and accept an ``AsyncSession``.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        # Cache health scores by app_id to avoid repeated computation within
        # the same topology call
        self._health_cache: Dict[UUID, ServiceHealthScore] = {}

    # ------------------------------------------------------------------
    # calculate_health
    # ------------------------------------------------------------------

    async def calculate_health(self, app_id: UUID) -> ServiceHealthScore:
        """
        Compute a composite health score for the given application.

        Args:
            app_id: UUID of the application.

        Returns:
            A ``ServiceHealthScore`` with per-factor breakdown.

        Raises:
            ValueError: If the application is not found.
        """
        if app_id in self._health_cache:
            return self._health_cache[app_id]

        # Load application
        app_result = await self.db.execute(
            select(Application).where(Application.id == app_id)
        )
        app = app_result.scalar_one_or_none()
        if app is None:
            raise ValueError(f"Application {app_id} not found.")

        # Compute each factor
        alert_factor = await self._factor_alerts(app_id)
        exec_factor = await self._factor_execution(app_id)
        dep_factor = await self._factor_dependency(app_id)
        change_factor = await self._factor_change_risk(app_id)

        all_factors = [alert_factor, exec_factor, dep_factor, change_factor]

        # Redistribute weights for factors with no data
        score, factors_with_weights = self._redistribute_and_score(all_factors)

        # Hard dependency cascade: if any hard dep is critical, force overall ≤20
        if dep_factor.hard_critical:
            score = min(score, 20.0)

        # Count alerts for summary fields
        active_count, critical_count = await self._count_alerts(app_id)

        # Determine status
        if all(f.weight == 0.0 for f in factors_with_weights):
            status = "unknown"
            score = 0.0
        else:
            status = _score_to_status(score)

        health = ServiceHealthScore(
            app_id=app_id,
            app_name=app.name,
            score=round(score, 2),
            status=status,
            factors=factors_with_weights,
            active_alerts=active_count,
            critical_alerts=critical_count,
            computed_at=_utc_now(),
        )
        self._health_cache[app_id] = health
        return health

    # ------------------------------------------------------------------
    # get_topology
    # ------------------------------------------------------------------

    async def get_topology(
        self, app_id: Optional[UUID] = None
    ) -> TopologyGraph:
        """
        Build a D3.js-compatible topology graph.

        Args:
            app_id: If provided, limit nodes to this application's components
                    plus their transitive dependencies.

        Returns:
            A ``TopologyGraph`` with nodes and edges.
        """
        # Load components (optionally scoped to one app)
        comp_stmt = select(ApplicationComponent)
        if app_id is not None:
            comp_stmt = comp_stmt.where(ApplicationComponent.app_id == app_id)
        comp_result = await self.db.execute(comp_stmt)
        components: List[ApplicationComponent] = comp_result.scalars().all()

        if not components:
            return TopologyGraph(nodes=[], edges=[], computed_at=_utc_now())

        component_ids = [c.id for c in components]

        # Load dependencies involving these components
        dep_stmt = select(ComponentDependency).where(
            ComponentDependency.from_component_id.in_(component_ids)
        )
        dep_result = await self.db.execute(dep_stmt)
        dependencies: List[ComponentDependency] = dep_result.scalars().all()

        # Load unique app IDs we need to resolve health scores for
        app_ids: Set[UUID] = {c.app_id for c in components}

        # Load app names
        app_map = await self._load_app_map(app_ids)

        # Build nodes
        nodes: List[TopologyNode] = []
        for comp in components:
            parent_app_id = comp.app_id
            app_name = app_map.get(parent_app_id, "Unknown")

            # Get health score for this app (cached after first call)
            health_score: Optional[float] = None
            health_status = "unknown"
            try:
                health = await self.calculate_health(parent_app_id)
                health_score = health.score
                health_status = health.status
            except Exception:
                pass

            nodes.append(
                TopologyNode(
                    id=str(comp.id),
                    name=comp.name,
                    type=comp.component_type or "unknown",
                    app_id=str(parent_app_id),
                    app_name=app_name,
                    health_score=health_score,
                    health_status=health_status,
                    is_hard_dependency=None,
                )
            )

        # Build edges
        edges: List[TopologyEdge] = []
        for dep in dependencies:
            # Determine failure_impact: "hard" or "soft"
            failure_impact = _classify_failure_impact(dep)
            edges.append(
                TopologyEdge(
                    source=str(dep.from_component_id),
                    target=str(dep.to_component_id),
                    type=dep.dependency_type or "sync",
                    failure_impact=failure_impact,
                )
            )

        return TopologyGraph(
            nodes=nodes,
            edges=edges,
            computed_at=_utc_now(),
        )

    # ------------------------------------------------------------------
    # Private: individual factor computation
    # ------------------------------------------------------------------

    async def _factor_alerts(self, app_id: UUID) -> "_FactorData":
        """Factor 1: Active Alerts (default weight 40%)."""
        from app.models import Alert

        result = await self.db.execute(
            select(Alert).where(
                and_(Alert.app_id == app_id, Alert.status == "firing")
            )
        )
        alerts = result.scalars().all()

        if not alerts:
            # Check if there are *any* historical alerts
            any_result = await self.db.execute(
                select(func.count(Alert.id)).where(Alert.app_id == app_id)
            )
            total = any_result.scalar_one()
            if total == 0:
                return _FactorData(
                    name=FACTOR_ALERTS,
                    default_weight=0.40,
                    has_data=False,
                    score=100.0,
                    detail="No alerts ever recorded for this app",
                )
            return _FactorData(
                name=FACTOR_ALERTS,
                default_weight=0.40,
                has_data=True,
                score=100.0,
                detail="No active alerts",
            )

        # Severity penalties
        penalty = 0.0
        for alert in alerts:
            sev = (alert.severity or "info").lower()
            if sev == "critical":
                penalty += 40.0
            elif sev == "warning":
                penalty += 15.0
            else:
                penalty += 5.0

        score = max(0.0, 100.0 - penalty)
        detail = (
            f"{len(alerts)} active alert(s); "
            f"penalty={penalty:.0f} pts"
        )
        return _FactorData(
            name=FACTOR_ALERTS,
            default_weight=0.40,
            has_data=True,
            score=score,
            detail=detail,
        )

    async def _factor_execution(self, app_id: UUID) -> "_FactorData":
        """Factor 2: Execution Success Rate (default weight 25%)."""
        try:
            from app.models_remediation import RunbookExecution
            from app.models_learning import ExecutionOutcome

            # Recent executions for runbooks linked to this app's alerts
            from app.models import Alert

            since = _utc_now() - timedelta(days=30)
            stmt = (
                select(RunbookExecution)
                .join(Alert, RunbookExecution.alert_id == Alert.id)
                .where(
                    and_(
                        Alert.app_id == app_id,
                        RunbookExecution.completed_at >= since,
                    )
                )
            )
            result = await self.db.execute(stmt)
            executions = result.scalars().all()

            if not executions:
                return _FactorData(
                    name=FACTOR_EXECUTION,
                    default_weight=0.25,
                    has_data=False,
                    score=50.0,
                    detail="No recent runbook executions",
                )

            total = len(executions)
            successful = sum(
                1
                for e in executions
                if e.status in ("success", "completed")
            )
            rate = successful / total
            return _FactorData(
                name=FACTOR_EXECUTION,
                default_weight=0.25,
                has_data=True,
                score=rate * 100.0,
                detail=f"{successful}/{total} executions succeeded (last 30 days)",
            )
        except Exception as exc:
            logger.debug("Execution factor unavailable: %s", exc)
            return _FactorData(
                name=FACTOR_EXECUTION,
                default_weight=0.25,
                has_data=False,
                score=50.0,
                detail="Execution data unavailable",
            )

    async def _factor_dependency(self, app_id: UUID) -> "_FactorData":
        """Factor 3: Dependency Health (default weight 20%)."""
        # Get components for this app
        comp_result = await self.db.execute(
            select(ApplicationComponent).where(ApplicationComponent.app_id == app_id)
        )
        components = comp_result.scalars().all()

        if not components:
            return _FactorData(
                name=FACTOR_DEPENDENCY,
                default_weight=0.20,
                has_data=False,
                score=100.0,
                detail="No components registered",
            )

        component_ids = [c.id for c in components]

        dep_result = await self.db.execute(
            select(ComponentDependency).where(
                ComponentDependency.from_component_id.in_(component_ids)
            )
        )
        dependencies = dep_result.scalars().all()

        if not dependencies:
            return _FactorData(
                name=FACTOR_DEPENDENCY,
                default_weight=0.20,
                has_data=False,
                score=100.0,
                detail="No dependencies defined",
            )

        # BFS traversal with cycle detection
        dep_app_ids = await self._collect_dependency_app_ids(
            component_ids, visited=set(component_ids)
        )

        if not dep_app_ids:
            return _FactorData(
                name=FACTOR_DEPENDENCY,
                default_weight=0.20,
                has_data=False,
                score=100.0,
                detail="No dependency apps found",
            )

        # Compute health for each dependency app
        dep_scores: List[Tuple[float, str]] = []  # (score, failure_impact)
        for dep_app_id in dep_app_ids:
            if dep_app_id == app_id:
                continue
            failure_impact = await self._get_dependency_impact_type(
                component_ids, dep_app_id
            )
            try:
                dep_health = await self.calculate_health(dep_app_id)
                dep_scores.append((dep_health.score, failure_impact))
            except Exception:
                dep_scores.append((0.0, failure_impact))

        if not dep_scores:
            return _FactorData(
                name=FACTOR_DEPENDENCY,
                default_weight=0.20,
                has_data=False,
                score=100.0,
                detail="Dependencies not scoreable",
            )

        # Apply impact rules
        score = 100.0
        hard_critical = False
        for dep_score, impact in dep_scores:
            if impact == "hard" and dep_score < 30:
                hard_critical = True
            elif impact == "soft" and dep_score < 50:
                score *= 0.85  # reduce by 15%

        if hard_critical:
            score = min(score, 20.0)

        avg_dep = sum(s for s, _ in dep_scores) / len(dep_scores)
        return _FactorData(
            name=FACTOR_DEPENDENCY,
            default_weight=0.20,
            has_data=True,
            score=score,
            detail=f"Avg dependency health: {avg_dep:.1f}; "
                   f"hard_critical={hard_critical}",
            hard_critical=hard_critical,
        )

    async def _factor_change_risk(self, app_id: UUID) -> "_FactorData":
        """Factor 4: Change Risk (default weight 15%)."""
        try:
            from app.models_itsm import ChangeImpactAnalysis, ChangeEvent

            since = _utc_now() - timedelta(days=7)
            stmt = (
                select(ChangeImpactAnalysis)
                .join(ChangeEvent, ChangeImpactAnalysis.change_event_id == ChangeEvent.id)
                .where(ChangeEvent.timestamp >= since)
            )
            result = await self.db.execute(stmt)
            analyses = result.scalars().all()

            if not analyses:
                return _FactorData(
                    name=FACTOR_CHANGE,
                    default_weight=0.15,
                    has_data=False,
                    score=100.0,
                    detail="No recent change impact analyses",
                )

            avg_corr = sum(a.correlation_score for a in analyses) / len(analyses)
            score = max(0.0, 100.0 - avg_corr * 100.0)
            return _FactorData(
                name=FACTOR_CHANGE,
                default_weight=0.15,
                has_data=True,
                score=score,
                detail=f"Avg change correlation: {avg_corr:.2f}",
            )
        except Exception as exc:
            logger.debug("Change risk factor unavailable: %s", exc)
            return _FactorData(
                name=FACTOR_CHANGE,
                default_weight=0.15,
                has_data=False,
                score=100.0,
                detail="Change data unavailable",
            )

    # ------------------------------------------------------------------
    # Private: helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _redistribute_and_score(
        factors: List[_FactorData],
    ) -> Tuple[float, List[HealthFactor]]:
        """
        Redistribute weights among factors that have data and compute overall score.

        Returns:
            (overall_score, list of HealthFactor with actual weights filled in)
        """
        available = [f for f in factors if f.has_data]
        total_weight = sum(f.default_weight for f in available)

        result_factors: List[HealthFactor] = []
        if not available or total_weight == 0:
            for f in factors:
                result_factors.append(
                    HealthFactor(
                        name=f.name,
                        weight=0.0,
                        score=f.score,
                        detail=f.detail,
                    )
                )
            return 0.0, result_factors

        overall = 0.0
        for f in factors:
            if f.has_data:
                actual_weight = f.default_weight / total_weight
                overall += actual_weight * f.score
            else:
                actual_weight = 0.0
            result_factors.append(
                HealthFactor(
                    name=f.name,
                    weight=round(actual_weight, 4),
                    score=round(f.score, 2),
                    detail=f.detail,
                )
            )

        return overall, result_factors

    async def _count_alerts(self, app_id: UUID) -> Tuple[int, int]:
        """Return (active_count, critical_count) for the application."""
        from app.models import Alert

        active_result = await self.db.execute(
            select(func.count(Alert.id)).where(
                and_(Alert.app_id == app_id, Alert.status == "firing")
            )
        )
        active = active_result.scalar_one() or 0

        critical_result = await self.db.execute(
            select(func.count(Alert.id)).where(
                and_(
                    Alert.app_id == app_id,
                    Alert.status == "firing",
                    Alert.severity == "critical",
                )
            )
        )
        critical = critical_result.scalar_one() or 0
        return int(active), int(critical)

    async def _collect_dependency_app_ids(
        self,
        component_ids: List[UUID],
        visited: Set[UUID],
    ) -> Set[UUID]:
        """BFS over ComponentDependency edges to collect all dependent app IDs."""
        dep_app_ids: Set[UUID] = set()
        queue = list(component_ids)

        while queue:
            batch = queue[:]
            queue = []

            dep_result = await self.db.execute(
                select(ComponentDependency).where(
                    ComponentDependency.from_component_id.in_(batch)
                )
            )
            deps = dep_result.scalars().all()

            for dep in deps:
                target_id = dep.to_component_id
                if target_id in visited:
                    continue
                visited.add(target_id)

                # Look up app_id for this component
                comp_result = await self.db.execute(
                    select(ApplicationComponent).where(
                        ApplicationComponent.id == target_id
                    )
                )
                comp = comp_result.scalar_one_or_none()
                if comp:
                    dep_app_ids.add(comp.app_id)
                    queue.append(target_id)

        return dep_app_ids

    async def _get_dependency_impact_type(
        self,
        from_component_ids: List[UUID],
        dep_app_id: UUID,
    ) -> str:
        """
        Determine whether the dependency relationship is 'hard' or 'soft'.

        Returns 'hard' if there is at least one dependency edge with
        ``dependency_type != 'optional'``, otherwise 'soft'.
        """
        # Get components for the dependency app
        comp_result = await self.db.execute(
            select(ApplicationComponent).where(
                ApplicationComponent.app_id == dep_app_id
            )
        )
        dep_comps = comp_result.scalars().all()
        dep_comp_ids = [c.id for c in dep_comps]

        dep_result = await self.db.execute(
            select(ComponentDependency).where(
                and_(
                    ComponentDependency.from_component_id.in_(from_component_ids),
                    ComponentDependency.to_component_id.in_(dep_comp_ids),
                )
            )
        )
        deps = dep_result.scalars().all()

        for d in deps:
            if d.dependency_type != "optional":
                return "hard"
        return "soft"

    async def _load_app_map(self, app_ids: Set[UUID]) -> Dict[UUID, str]:
        """Return {app_id: app_name} for the given set of app IDs."""
        if not app_ids:
            return {}
        result = await self.db.execute(
            select(Application).where(Application.id.in_(app_ids))
        )
        return {a.id: a.name for a in result.scalars().all()}


# ---------------------------------------------------------------------------
# Internal data structure
# ---------------------------------------------------------------------------

class _FactorData:
    """Internal holder for a health factor before weight redistribution."""

    __slots__ = ("name", "default_weight", "has_data", "score", "detail", "hard_critical")

    def __init__(
        self,
        name: str,
        default_weight: float,
        has_data: bool,
        score: float,
        detail: str,
        hard_critical: bool = False,
    ) -> None:
        self.name = name
        self.default_weight = default_weight
        self.has_data = has_data
        self.score = score
        self.detail = detail
        self.hard_critical = hard_critical


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _classify_failure_impact(dep: ComponentDependency) -> str:
    """Map dependency_type to failure_impact label."""
    if dep.dependency_type == "optional":
        return "soft"
    return "hard"
