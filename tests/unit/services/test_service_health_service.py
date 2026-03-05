"""
Unit tests for ServiceHealthService (Feature A2).
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4


def _utc(offset_minutes: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(name: str = "my-app") -> MagicMock:
    app = MagicMock()
    app.id = uuid4()
    app.name = name
    return app


def _make_alert(severity: str = "warning", status: str = "firing") -> MagicMock:
    a = MagicMock()
    a.id = uuid4()
    a.severity = severity
    a.status = status
    return a


def _make_execution(exec_status: str = "success") -> MagicMock:
    ex = MagicMock()
    ex.id = uuid4()
    ex.status = exec_status
    return ex


def _make_component(app_id=None) -> MagicMock:
    c = MagicMock()
    c.id = uuid4()
    c.app_id = app_id or uuid4()
    c.name = "api-server"
    c.component_type = "compute"
    return c


def _make_dependency(
    from_id=None,
    to_id=None,
    dep_type: str = "sync",
    failure_impact: str = "Service becomes unavailable",
) -> MagicMock:
    d = MagicMock()
    d.id = uuid4()
    d.from_component_id = from_id or uuid4()
    d.to_component_id = to_id or uuid4()
    d.dependency_type = dep_type
    d.failure_impact = failure_impact
    return d


def _make_service():
    """Create ServiceHealthService with a mocked AsyncSession."""
    from app.services.service_health_service import ServiceHealthService

    db = AsyncMock()
    return ServiceHealthService(db)


def _scalar_result(value):
    """Return an AsyncMock execute result for scalar_one_or_none."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _scalars_result(values):
    """Return an AsyncMock execute result for scalars().all()."""
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


def _scalar_one_result(value):
    """Return an AsyncMock execute result for scalar_one()."""
    r = MagicMock()
    r.scalar_one.return_value = value
    return r


# ---------------------------------------------------------------------------
# calculate_health — application not found
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_health_app_not_found():
    """calculate_health raises HTTP 404 when app_id does not exist."""
    from fastapi import HTTPException

    svc = _make_service()

    app_result = _scalar_result(None)
    svc.db.execute = AsyncMock(return_value=app_result)

    with pytest.raises(HTTPException) as exc_info:
        await svc.calculate_health(uuid4())

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# calculate_health — healthy app
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_health_healthy_app():
    """App with no firing alerts and successful executions → score ≥ 80, 'healthy'."""
    svc = _make_service()
    app = _make_app("api-service")

    # execute() call sequence:
    # 1. select Application → app
    # 2. select firing Alert → []
    # 3. count all Alert → 10 (has alert history)
    # 4. select RunbookExecution join Alert → [success, success]
    # 5. select ApplicationComponent → []  (no deps → skip dep factor)
    # 6. select Application for change risk
    # 7. select ChangeImpactAnalysis → []

    svc.db.execute = AsyncMock(
        side_effect=[
            _scalar_result(app),              # 1. app lookup
            _scalars_result([]),              # 2. firing alerts
            _scalar_one_result(10),           # 3. any alerts count
            _scalars_result([                 # 4. executions
                _make_execution("success"),
                _make_execution("success"),
            ]),
            _scalars_result([]),              # 5. components (no deps)
            _scalar_result(app),              # 6. app for change risk
            _scalars_result([]),              # 7. change impact records
        ]
    )

    score = await svc.calculate_health(app.id)

    assert score.score >= 80.0
    assert score.status == "healthy"
    assert score.active_alerts == 0
    assert score.app_name == "api-service"


# ---------------------------------------------------------------------------
# calculate_health — degraded app
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_health_degraded_app():
    """App with warning alerts → score 50-79, 'degraded'."""
    svc = _make_service()
    app = _make_app("worker-service")

    warning_alerts = [_make_alert("warning"), _make_alert("warning")]

    svc.db.execute = AsyncMock(
        side_effect=[
            _scalar_result(app),
            _scalars_result(warning_alerts),   # 2 warning alerts firing
            _scalar_one_result(5),             # has alert history
            _scalars_result([]),               # no executions
            _scalars_result([]),               # no components
            _scalar_result(app),
            _scalars_result([]),               # no change impact
        ]
    )

    score = await svc.calculate_health(app.id)

    assert 50.0 <= score.score < 80.0
    assert score.status == "degraded"


# ---------------------------------------------------------------------------
# calculate_health — critical app (critical alert)
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_health_critical_app():
    """App with critical alert firing → score < 50, 'critical'."""
    svc = _make_service()
    app = _make_app("db-service")

    critical_alerts = [_make_alert("critical"), _make_alert("critical")]

    svc.db.execute = AsyncMock(
        side_effect=[
            _scalar_result(app),
            _scalars_result(critical_alerts),
            _scalar_one_result(5),
            _scalars_result([]),
            _scalars_result([]),
            _scalar_result(app),
            _scalars_result([]),
        ]
    )

    score = await svc.calculate_health(app.id)

    assert score.score < 50.0
    assert score.status == "critical"
    assert score.critical_alerts == 2


# ---------------------------------------------------------------------------
# calculate_health — unknown status (no data at all)
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_calculate_health_unknown_when_no_data():
    """App with no alert history, no executions, no deps, no changes → 'unknown'."""
    svc = _make_service()
    app = _make_app("brand-new-app")

    svc.db.execute = AsyncMock(
        side_effect=[
            _scalar_result(app),
            _scalars_result([]),   # no firing alerts
            _scalar_one_result(0), # no alert history at all
            _scalars_result([]),   # no executions
            _scalars_result([]),   # no components
            _scalar_result(app),
            _scalars_result([]),   # no change impact
        ]
    )

    score = await svc.calculate_health(app.id)

    assert score.status == "unknown"


# ---------------------------------------------------------------------------
# calculate_health — weight redistribution
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_weight_redistribution_when_two_factors_have_no_data():
    """When 2 factors have no data, remaining 2 factors should share 100% weight."""
    svc = _make_service()
    app = _make_app("partial-app")

    svc.db.execute = AsyncMock(
        side_effect=[
            _scalar_result(app),
            _scalars_result([_make_alert("warning")]),  # factor 1 has data
            _scalar_one_result(5),
            _scalars_result([_make_execution("success")]),  # factor 2 has data
            _scalars_result([]),   # no components → factor 3 no data
            _scalar_result(app),
            _scalars_result([]),   # no change impact → factor 4 no data
        ]
    )

    score = await svc.calculate_health(app.id)

    factors_with_data = [f for f in score.factors if f.weight > 0]
    assert len(factors_with_data) == 2
    total_weight = sum(f.weight for f in score.factors)
    assert abs(total_weight - 1.0) < 0.01  # weights should sum to ~1.0


# ---------------------------------------------------------------------------
# calculate_health — circular dependency safety
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_circular_dependency_does_not_cause_infinite_loop():
    """BFS cycle detection prevents infinite loops in circular dependency graphs.

    App A (comp_a) → depends on → dep_app B (comp_b) → depends back on → comp_a.
    The _computing guard prevents infinite recursion.
    """
    svc = _make_service()
    app = _make_app("circular-app")
    dep_app = _make_app("dep-app")

    comp_a = _make_component(app_id=app.id)
    comp_b = _make_component(app_id=dep_app.id)
    dep_a_to_b = _make_dependency(comp_a.id, comp_b.id, "sync")
    dep_b_to_a = _make_dependency(comp_b.id, comp_a.id, "sync")  # circular!

    # Full mock call sequence (20 execute() calls):
    svc.db.execute = AsyncMock(
        side_effect=[
            # calculate_health(app.id) — _calculate_health_inner
            _scalar_result(app),                # 1.  app lookup
            _scalars_result([]),                # 2.  firing alerts
            _scalar_one_result(0),             # 3.  any alerts count → no history
            _scalars_result([]),                # 4.  executions
            # _compute_dependency_factor(app.id) BFS
            _scalars_result([comp_a]),          # 5.  components of app
            _scalars_result([dep_a_to_b]),      # 6.  direct deps from comp_a
            _scalar_result(comp_b),             # 7.  comp_b lookup → dep_app.id
            _scalars_result([dep_b_to_a]),      # 8.  comp_b outgoing → comp_a (visited → skip)
            # recursive calculate_health(dep_app.id) — dep_app NOT in _computing yet
            _scalar_result(dep_app),            # 9.  dep_app lookup
            _scalars_result([]),                # 10. dep_app firing alerts
            _scalar_one_result(0),             # 11. dep_app any alerts
            _scalars_result([]),                # 12. dep_app executions
            # _compute_dependency_factor(dep_app.id) BFS
            _scalars_result([comp_b]),          # 13. components of dep_app
            _scalars_result([dep_b_to_a]),      # 14. direct deps from comp_b
            _scalar_result(comp_a),             # 15. comp_a lookup → app.id (in _computing → returns unknown)
            _scalars_result([dep_a_to_b]),      # 16. comp_a outgoing → comp_b (visited → skip)
            # _compute_change_risk_factor(dep_app.id)
            _scalar_result(dep_app),            # 17. dep_app for change risk
            _scalars_result([]),                # 18. change impact records (empty)
            # _compute_change_risk_factor(app.id)
            _scalar_result(app),               # 19. app for change risk
            _scalars_result([]),               # 20. change impact records (empty)
        ]
    )

    # Test must complete without hanging or crashing
    try:
        score = await svc.calculate_health(app.id)
        assert score is not None
    except Exception as exc:
        pytest.fail(f"calculate_health raised an unexpected exception on circular dependency: {exc}")


# ---------------------------------------------------------------------------
# calculate_health — isolated component (no deps, weight redistributed)
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_isolated_component_dep_factor_weight_zero():
    """App with no dependencies has factor 3 weight = 0 (redistributed)."""
    svc = _make_service()
    app = _make_app("isolated-app")

    svc.db.execute = AsyncMock(
        side_effect=[
            _scalar_result(app),
            _scalars_result([]),              # no firing alerts
            _scalar_one_result(5),
            _scalars_result([_make_execution("success")]),
            _scalars_result([_make_component(app_id=app.id)]),  # has components
            _scalars_result([]),              # but no outgoing deps
            _scalar_result(app),
            _scalars_result([]),             # no change impact
        ]
    )

    score = await svc.calculate_health(app.id)

    dep_factor = next((f for f in score.factors if f.name == "dependency_health"), None)
    assert dep_factor is not None
    assert dep_factor.weight == 0.0


# ---------------------------------------------------------------------------
# get_topology — D3.js-compatible output
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_topology_returns_nodes_and_edges():
    """get_topology returns nodes and edges in D3.js-compatible format."""
    svc = _make_service()
    app = _make_app("topology-app")
    comp_a = _make_component(app_id=app.id)
    comp_b = _make_component(app_id=app.id)
    dep = _make_dependency(comp_a.id, comp_b.id, "sync")

    svc.db.execute = AsyncMock(
        side_effect=[
            _scalars_result([comp_a, comp_b]),  # components
            _scalars_result([dep]),              # dependencies
            _scalars_result([app]),              # apps for names
            # calculate_health for app
            _scalar_result(app),
            _scalars_result([]),
            _scalar_one_result(0),
            _scalars_result([]),
            _scalars_result([]),
            _scalar_result(app),
            _scalars_result([]),
        ]
    )

    graph = await svc.get_topology(app_id=app.id)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.edges[0].failure_impact == "hard"
    assert graph.edges[0].type == "sync"
    # Nodes should have id as strings
    assert all(isinstance(n.id, str) for n in graph.nodes)


# ---------------------------------------------------------------------------
# get_topology — empty (no components)
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_topology_empty_when_no_components():
    """get_topology returns empty graph when no components exist."""
    svc = _make_service()

    svc.db.execute = AsyncMock(
        return_value=_scalars_result([])
    )

    graph = await svc.get_topology(app_id=uuid4())

    assert graph.nodes == []
    assert graph.edges == []
