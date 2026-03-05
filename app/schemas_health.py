"""
Schemas for Service Health Score & Topology API (Feature A2).
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class HealthFactor(BaseModel):
    """A single contributing factor to a service health score."""

    name: str  # "active_alerts", "execution_success", "dependency_health", "change_risk"
    weight: float  # Actual weight used after redistribution
    score: float  # 0–100 for this factor
    detail: str  # Human-readable explanation


class ServiceHealthScore(BaseModel):
    """Composite health score for an application."""

    app_id: UUID
    app_name: str
    score: float  # 0–100
    status: str  # "healthy", "degraded", "critical", "unknown"
    factors: List[HealthFactor]
    active_alerts: int
    critical_alerts: int
    computed_at: datetime


class ApplicationHealthListResponse(BaseModel):
    """Paginated list of application health scores."""

    items: List[ServiceHealthScore]
    total: int


class TopologyNode(BaseModel):
    """A single node in the service topology graph."""

    id: str  # Component UUID as string
    name: str
    type: str  # Component type (web, database, cache, queue, etc.)
    app_id: str
    app_name: str
    health_score: Optional[float] = None
    health_status: str
    is_hard_dependency: Optional[bool] = None  # Null for root nodes


class TopologyEdge(BaseModel):
    """A directed dependency edge in the service topology graph."""

    source: str  # Component UUID
    target: str  # Component UUID
    type: str  # Dependency type
    failure_impact: str  # "hard" or "soft"


class TopologyGraph(BaseModel):
    """D3.js-compatible topology graph for a service or the entire fleet."""

    nodes: List[TopologyNode]
    edges: List[TopologyEdge]
    computed_at: datetime
