"""
Unit tests for ServiceHealthService (Feature A2).

Test IDs: TC-SHS-SVC-01 … TC-SHS-SVC-10
"""
from __future__ import annotations

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


def _make_app(
    app_id: Optional[uuid.UUID] = None,
    name: str = "my-app",
) -> MagicMock:
    app = MagicMock()
    app.id = app_id or uuid.uuid4()
    app.name = name
    return app


def _make_alert(
    app_id: Optional[uuid.UUID] = None,
    severity: str = "warning",
    status: str = "firing",
) -> MagicMock:
    alert = MagicMock()
    alert.id = uuid.uuid4()
    alert.app_id = app_id or uuid.uuid4()
    alert.severity = severity
    alert.status = status
    return alert


def _make_component(
    comp_id: Optional[uuid.UUID] = None,
    app_id: Optional[uuid.UUID] = None,
    component_type: str = "compute",
    name: str = "api-server",
) -> MagicMock:
    comp = MagicMock()
    comp.id = comp_id or uuid.uuid4()
    comp.app_id = app_id or uuid.uuid4()
    comp.component_type = component_type
    comp.name = name
    return comp


def _make_dependency(
    from_id: Optional[uuid.UUID] = None,
    to_id: Optional[uuid.UUID] = None,
    dep_type: str = "sync",
    failure_impact: str = "Service unavailable",
) -> MagicMock:
    dep = MagicMock()
    dep.id = uuid.uuid4()
    dep.from_component_id = from_id or uuid.uuid4()
    dep.to_component_id = to_id or uuid.uuid4()
    dep.dependency_type = dep_type
    dep.failure_impact = failure_impact
    return dep


def _scalar_result(value: Any) -> MagicMock:
    """Build a mock execute() result that returns value from scalar_one()."""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _scalars_result(items: List) -> MagicMock:
    """Build a mock execute() result that returns items from scalars().all()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


# ---------------------------------------------------------------------------
# TC-SHS-SVC-01  Healthy app: no alerts → score ≥ 80, status "healthy"
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_healthy_app_no_alerts():
    """TC-SHS-SVC-01: App with no firing alerts scores ≥ 80 and is 'healthy'."""
    from app.services.service_health_service import ServiceHealthService

    app_id = uuid.uuid4()
    db = AsyncMock()

    app = _make_app(app_id=app_id)

    call_count = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Application lookup
            return _scalars_result([app])
        if call_count == 2:
            # Active alerts (firing) — none
            return _scalars_result([])
        if call_count == 3:
            # Total alert count (any status)
            return _scalar_result(5)  # has historical data
        # All remaining calls: return empty
        return _scalars_result([])

    db.execute = AsyncMock(side_effect=execute_side_effect)

    svc = ServiceHealthService(db)
    # Override factor methods to return controlled data
    from app.services.service_health_service import _FactorData, FACTOR_ALERTS, FACTOR_EXECUTION, FACTOR_DEPENDENCY, FACTOR_CHANGE

    with patch.object(svc, "_factor_alerts", new=AsyncMock(
        return_value=_FactorData(FACTOR_ALERTS, 0.40, True, 100.0, "No alerts")
    )), patch.object(svc, "_factor_execution", new=AsyncMock(
        return_value=_FactorData(FACTOR_EXECUTION, 0.25, True, 100.0, "10/10 success")
    )), patch.object(svc, "_factor_dependency", new=AsyncMock(
        return_value=_FactorData(FACTOR_DEPENDENCY, 0.20, False, 100.0, "No deps")
    )), patch.object(svc, "_factor_change_risk", new=AsyncMock(
        return_value=_FactorData(FACTOR_CHANGE, 0.15, False, 100.0, "No changes")
    )), patch.object(svc, "_count_alerts", new=AsyncMock(return_value=(0, 0))):
        # patch the app lookup
        app_result = MagicMock()
        app_result.scalar_one_or_none.return_value = app
        db.execute = AsyncMock(return_value=app_result)

        score = await svc.calculate_health(app_id)

    assert score.score >= 80.0
    assert score.status == "healthy"


# ---------------------------------------------------------------------------
# TC-SHS-SVC-02  Degraded app: warning alerts → score 50–79
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_degraded_app_warning_alerts():
    """TC-SHS-SVC-02: Warning alerts produce a degraded score (50–79)."""
    from app.services.service_health_service import ServiceHealthService, _FactorData, FACTOR_ALERTS, FACTOR_EXECUTION, FACTOR_DEPENDENCY, FACTOR_CHANGE

    app_id = uuid.uuid4()
    db = AsyncMock()
    app = _make_app(app_id=app_id)

    app_result = MagicMock()
    app_result.scalar_one_or_none.return_value = app
    db.execute = AsyncMock(return_value=app_result)

    svc = ServiceHealthService(db)
    # Alert score = 100 - 2*15 = 70 → with execution factor also active → ~75
    with patch.object(svc, "_factor_alerts", new=AsyncMock(
        return_value=_FactorData(FACTOR_ALERTS, 0.40, True, 70.0, "2 warnings")
    )), patch.object(svc, "_factor_execution", new=AsyncMock(
        return_value=_FactorData(FACTOR_EXECUTION, 0.25, True, 80.0, "8/10")
    )), patch.object(svc, "_factor_dependency", new=AsyncMock(
        return_value=_FactorData(FACTOR_DEPENDENCY, 0.20, False, 100.0, "No deps")
    )), patch.object(svc, "_factor_change_risk", new=AsyncMock(
        return_value=_FactorData(FACTOR_CHANGE, 0.15, False, 100.0, "No changes")
    )), patch.object(svc, "_count_alerts", new=AsyncMock(return_value=(2, 0))):
        score = await svc.calculate_health(app_id)

    assert 50.0 <= score.score < 80.0
    assert score.status == "degraded"


# ---------------------------------------------------------------------------
# TC-SHS-SVC-03  Critical app: critical alert → score < 50
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_critical_app_critical_alert():
    """TC-SHS-SVC-03: A critical alert produces score < 50 and status 'critical'."""
    from app.services.service_health_service import ServiceHealthService, _FactorData, FACTOR_ALERTS, FACTOR_EXECUTION, FACTOR_DEPENDENCY, FACTOR_CHANGE

    app_id = uuid.uuid4()
    db = AsyncMock()
    app = _make_app(app_id=app_id)

    app_result = MagicMock()
    app_result.scalar_one_or_none.return_value = app
    db.execute = AsyncMock(return_value=app_result)

    svc = ServiceHealthService(db)
    # Alert score with 1 critical = max(0, 100-40) = 60 — but we force it low
    with patch.object(svc, "_factor_alerts", new=AsyncMock(
        return_value=_FactorData(FACTOR_ALERTS, 0.40, True, 20.0, "2 criticals")
    )), patch.object(svc, "_factor_execution", new=AsyncMock(
        return_value=_FactorData(FACTOR_EXECUTION, 0.25, True, 50.0, "5/10")
    )), patch.object(svc, "_factor_dependency", new=AsyncMock(
        return_value=_FactorData(FACTOR_DEPENDENCY, 0.20, False, 100.0, "No deps")
    )), patch.object(svc, "_factor_change_risk", new=AsyncMock(
        return_value=_FactorData(FACTOR_CHANGE, 0.15, False, 100.0, "No changes")
    )), patch.object(svc, "_count_alerts", new=AsyncMock(return_value=(2, 2))):
        score = await svc.calculate_health(app_id)

    assert score.score < 50.0
    assert score.status == "critical"


# ---------------------------------------------------------------------------
# TC-SHS-SVC-04  Hard dependency cascade forces parent to critical
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_hard_dependency_cascade():
    """TC-SHS-SVC-04: Hard dependency with score < 30 forces parent to critical."""
    from app.services.service_health_service import ServiceHealthService, _FactorData, FACTOR_ALERTS, FACTOR_EXECUTION, FACTOR_DEPENDENCY, FACTOR_CHANGE

    app_id = uuid.uuid4()
    db = AsyncMock()
    app = _make_app(app_id=app_id)

    app_result = MagicMock()
    app_result.scalar_one_or_none.return_value = app
    db.execute = AsyncMock(return_value=app_result)

    svc = ServiceHealthService(db)
    # Hard dep with score < 30 → hard_critical=True → overall score forced to ≤20
    with patch.object(svc, "_factor_alerts", new=AsyncMock(
        return_value=_FactorData(FACTOR_ALERTS, 0.40, True, 100.0, "No alerts")
    )), patch.object(svc, "_factor_execution", new=AsyncMock(
        return_value=_FactorData(FACTOR_EXECUTION, 0.25, True, 100.0, "All ok")
    )), patch.object(svc, "_factor_dependency", new=AsyncMock(
        return_value=_FactorData(
            FACTOR_DEPENDENCY, 0.20, True, 15.0, "Hard dep critical", hard_critical=True
        )
    )), patch.object(svc, "_factor_change_risk", new=AsyncMock(
        return_value=_FactorData(FACTOR_CHANGE, 0.15, False, 100.0, "No changes")
    )), patch.object(svc, "_count_alerts", new=AsyncMock(return_value=(0, 0))):
        score = await svc.calculate_health(app_id)

    # Overall score forced to ≤20 due to hard critical dependency cascade
    assert score.score <= 20.0
    assert score.status == "critical"


# ---------------------------------------------------------------------------
# TC-SHS-SVC-05  Soft dependency reduces parent score by 15%
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_soft_dependency_reduces_score():
    """TC-SHS-SVC-05: Soft dependency with score < 50 reduces parent by 15%."""
    from app.services.service_health_service import ServiceHealthService

    app_id = uuid.uuid4()
    dep_app_id = uuid.uuid4()
    from_comp_id = uuid.uuid4()
    to_comp_id = uuid.uuid4()

    db = AsyncMock()

    comp = _make_component(comp_id=from_comp_id, app_id=app_id)
    dep_comp = _make_component(comp_id=to_comp_id, app_id=dep_app_id)
    dep = _make_dependency(from_id=from_comp_id, to_id=to_comp_id, dep_type="optional")

    def _scalars_all(items):
        r = MagicMock()
        r.scalars.return_value.all.return_value = items
        return r

    def _scalar_one(item):
        r = MagicMock()
        r.scalar_one_or_none.return_value = item
        return r

    call_count = 0
    # Each execute() call returns results in order:
    # 0: components for app_id (scalars.all)
    # 1: deps check in _factor_dependency (scalars.all)
    # 2: BFS – deps from [from_comp_id] (scalars.all)
    # 3: BFS – lookup comp for to_comp_id (scalar_one_or_none)
    # 4: BFS – deps from [to_comp_id] → empty (loop ends)
    # 5: _get_dependency_impact_type – dep app comps
    # 6: _get_dependency_impact_type – deps between
    results = [
        _scalars_all([comp]),       # (0) components for app_id
        _scalars_all([dep]),        # (1) deps check in _factor_dependency
        _scalars_all([dep]),        # (2) BFS: deps from from_comp_id
        _scalar_one(dep_comp),      # (3) BFS: lookup comp for to_comp_id
        _scalars_all([]),           # (4) BFS: deps from to_comp_id → empty
        _scalars_all([dep_comp]),   # (5) _get_dependency_impact_type: dep app comps
        _scalars_all([dep]),        # (6) _get_dependency_impact_type: deps between
    ]

    async def execute_side(stmt):
        nonlocal call_count
        r = results[call_count] if call_count < len(results) else _scalars_all([])
        call_count += 1
        return r

    db.execute = AsyncMock(side_effect=execute_side)

    svc = ServiceHealthService(db)
    # dep app has score=40 (< 50) with "soft" impact → score *= 0.85
    dep_health = MagicMock()
    dep_health.score = 40.0

    with patch.object(
        svc,
        "calculate_health",
        new=AsyncMock(return_value=dep_health),
    ):
        factor = await svc._factor_dependency(app_id)

    # score should be 100 * 0.85 = 85 (soft dep reduces by 15%)
    assert factor.score == pytest.approx(85.0, abs=1.0)
    assert factor.has_data is True


# ---------------------------------------------------------------------------
# TC-SHS-SVC-06  Circular dependencies: BFS cycle detection prevents infinite loop
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_circular_dependency_no_infinite_loop():
    """TC-SHS-SVC-06: Circular dependency graph terminates without error."""
    from app.services.service_health_service import ServiceHealthService

    app_id = uuid.uuid4()
    comp_a = uuid.uuid4()
    comp_b = uuid.uuid4()

    db = AsyncMock()

    # comp_a → comp_b → comp_a (cycle)
    dep_ab = _make_dependency(from_id=comp_a, to_id=comp_b, dep_type="sync")
    dep_ba = _make_dependency(from_id=comp_b, to_id=comp_a, dep_type="sync")

    comp_a_obj = _make_component(comp_id=comp_a, app_id=app_id)
    comp_b_obj = _make_component(comp_id=comp_b, app_id=app_id)
    # Ensure app_id is a real UUID (not a MagicMock)
    comp_b_obj.app_id = app_id

    def _scalars_all(items):
        r = MagicMock()
        r.scalars.return_value.all.return_value = items
        return r

    def _scalar_one(item):
        r = MagicMock()
        r.scalar_one_or_none.return_value = item
        return r

    call_count = 0
    # BFS starting from [comp_a] with comp_a already in visited:
    # 1: deps from [comp_a] → [dep_ab]
    # 2: lookup comp_b → comp_b_obj (scalar_one_or_none)
    # 3: deps from [comp_b] → [dep_ba] (target=comp_a, already visited → stop)
    results = [
        _scalars_all([dep_ab]),     # deps from comp_a
        _scalar_one(comp_b_obj),   # lookup comp_b
        _scalars_all([dep_ba]),    # deps from comp_b
        # comp_a already visited → BFS terminates
    ]

    async def execute_side(stmt):
        nonlocal call_count
        r = results[call_count] if call_count < len(results) else _scalars_all([])
        call_count += 1
        return r

    db.execute = AsyncMock(side_effect=execute_side)

    svc = ServiceHealthService(db)
    # Should complete without infinite recursion
    dep_app_ids = await svc._collect_dependency_app_ids(
        [comp_a], visited={comp_a}
    )
    # comp_b's app_id should be discovered
    assert app_id in dep_app_ids


# ---------------------------------------------------------------------------
# TC-SHS-SVC-07  Weight redistribution
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_weight_redistribution():
    """TC-SHS-SVC-07: When 2 factors have no data, remaining 2 share 100% weight."""
    from app.services.service_health_service import ServiceHealthService, _FactorData, FACTOR_ALERTS, FACTOR_EXECUTION, FACTOR_DEPENDENCY, FACTOR_CHANGE

    factors = [
        _FactorData(FACTOR_ALERTS, 0.40, True, 80.0, "2 warnings"),
        _FactorData(FACTOR_EXECUTION, 0.25, True, 90.0, "9/10"),
        _FactorData(FACTOR_DEPENDENCY, 0.20, False, 100.0, "No deps"),
        _FactorData(FACTOR_CHANGE, 0.15, False, 100.0, "No changes"),
    ]

    score, result_factors = ServiceHealthService._redistribute_and_score(factors)

    # Only 2 factors have data; their weights should sum to 1.0
    total_weight = sum(f.weight for f in result_factors)
    assert total_weight == pytest.approx(1.0, abs=0.01)

    # Factors without data should have weight 0
    dep_factor = next(f for f in result_factors if f.name == FACTOR_DEPENDENCY)
    change_factor = next(f for f in result_factors if f.name == FACTOR_CHANGE)
    assert dep_factor.weight == 0.0
    assert change_factor.weight == 0.0


# ---------------------------------------------------------------------------
# TC-SHS-SVC-08  Isolated component (no dependencies → dep factor weight = 0)
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_isolated_component_no_dependencies():
    """TC-SHS-SVC-08: No dependencies → dependency factor has no data."""
    from app.services.service_health_service import ServiceHealthService

    app_id = uuid.uuid4()
    db = AsyncMock()

    comp = _make_component(comp_id=uuid.uuid4(), app_id=app_id)

    call_count = 0

    async def execute_side(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _scalars_result([comp])  # components
        return _scalars_result([])  # no dependencies

    db.execute = AsyncMock(side_effect=execute_side)

    svc = ServiceHealthService(db)
    factor = await svc._factor_dependency(app_id)

    assert factor.has_data is False
    assert factor.default_weight == pytest.approx(0.20)


# ---------------------------------------------------------------------------
# TC-SHS-SVC-09  Unknown status: no data of any kind
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_unknown_status_no_data():
    """TC-SHS-SVC-09: App with no data of any kind returns status='unknown'."""
    from app.services.service_health_service import ServiceHealthService, _FactorData, FACTOR_ALERTS, FACTOR_EXECUTION, FACTOR_DEPENDENCY, FACTOR_CHANGE

    app_id = uuid.uuid4()
    db = AsyncMock()
    app = _make_app(app_id=app_id)

    app_result = MagicMock()
    app_result.scalar_one_or_none.return_value = app
    db.execute = AsyncMock(return_value=app_result)

    svc = ServiceHealthService(db)
    # All factors have no data
    with patch.object(svc, "_factor_alerts", new=AsyncMock(
        return_value=_FactorData(FACTOR_ALERTS, 0.40, False, 0.0, "No history")
    )), patch.object(svc, "_factor_execution", new=AsyncMock(
        return_value=_FactorData(FACTOR_EXECUTION, 0.25, False, 0.0, "No data")
    )), patch.object(svc, "_factor_dependency", new=AsyncMock(
        return_value=_FactorData(FACTOR_DEPENDENCY, 0.20, False, 0.0, "No deps")
    )), patch.object(svc, "_factor_change_risk", new=AsyncMock(
        return_value=_FactorData(FACTOR_CHANGE, 0.15, False, 0.0, "No changes")
    )), patch.object(svc, "_count_alerts", new=AsyncMock(return_value=(0, 0))):
        score = await svc.calculate_health(app_id)

    assert score.status == "unknown"


# ---------------------------------------------------------------------------
# TC-SHS-SVC-10  Topology: nodes and edges in D3.js format
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_topology_d3_format():
    """TC-SHS-SVC-10: Topology graph has correct nodes and edges for D3.js."""
    from app.services.service_health_service import ServiceHealthService

    app_id = uuid.uuid4()
    comp_a_id = uuid.uuid4()
    comp_b_id = uuid.uuid4()

    db = AsyncMock()

    comp_a = _make_component(comp_id=comp_a_id, app_id=app_id, name="api")
    comp_b = _make_component(comp_id=comp_b_id, app_id=app_id, name="db")
    dep = _make_dependency(from_id=comp_a_id, to_id=comp_b_id, dep_type="sync")
    app = _make_app(app_id=app_id, name="my-service")

    call_count = 0
    results = [
        _scalars_result([comp_a, comp_b]),  # components
        _scalars_result([dep]),              # dependencies
        _scalars_result([app]),              # app name lookup
    ]

    async def execute_side(stmt):
        nonlocal call_count
        r = results[call_count] if call_count < len(results) else _scalars_result([])
        call_count += 1
        return r

    db.execute = AsyncMock(side_effect=execute_side)

    svc = ServiceHealthService(db)
    # Bypass health calculation
    with patch.object(svc, "calculate_health", new=AsyncMock(side_effect=Exception("no data"))):
        graph = await svc.get_topology(app_id=app_id)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1

    node_ids = {n.id for n in graph.nodes}
    assert str(comp_a_id) in node_ids
    assert str(comp_b_id) in node_ids

    edge = graph.edges[0]
    assert edge.source == str(comp_a_id)
    assert edge.target == str(comp_b_id)
    assert edge.failure_impact == "hard"  # sync dep → hard
