"""
Schemas for Service Health Score & Topology (Feature A2).

Provides request/response models for composite health scores per
application/component and D3.js-compatible topology data.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class HealthFactor(BaseModel):
    """A single factor that contributes to a service health score."""

    name: str
    weight: float = 0.0
    score: float = 0.0
    detail: str = ""


class ServiceHealthScore(BaseModel):
    """Composite health score for a single application."""

    app_id: UUID
    app_name: str
    score: float
    status: str  # healthy | degraded | critical | unknown
    factors: List[HealthFactor]
    active_alerts: int
    critical_alerts: int
    computed_at: datetime


class TopologyNode(BaseModel):
    """A node (component) in the service topology graph."""

    id: str
    name: str
    type: str
    app_id: str
    app_name: str
    health_score: Optional[float] = None
    health_status: str
    is_hard_dependency: Optional[bool] = None


class TopologyEdge(BaseModel):
    """A directed dependency edge in the topology graph."""

    source: str
    target: str
    type: str
    failure_impact: str  # hard | soft


class TopologyGraph(BaseModel):
    """D3.js-compatible topology graph."""

    nodes: List[TopologyNode]
    edges: List[TopologyEdge]
    computed_at: datetime


class ApplicationHealthListResponse(BaseModel):
    """Paginated list of application health scores."""

    items: List[ServiceHealthScore]
    total: int
