"""
Postmortem Report Pydantic Schemas
Request/Response models for post-incident review API.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TimelineEntry(BaseModel):
    """A single event in the incident timeline."""

    timestamp: datetime
    event: str
    source: str
    manual: bool = False


class ActionItem(BaseModel):
    """An actionable follow-up from the postmortem."""

    description: str
    owner: Optional[str] = None
    due_date: Optional[date] = None
    status: str = "open"  # open | in_progress | done


class RemediationAction(BaseModel):
    """A remediation action taken during the incident."""

    action: str
    runbook_id: Optional[UUID] = None
    outcome: Optional[str] = None
    duration_minutes: Optional[float] = None


class PostmortemMetrics(BaseModel):
    """Incident lifecycle metrics (all in minutes)."""

    mttd_minutes: Optional[float] = None  # Mean Time To Detect
    mtta_minutes: Optional[float] = None  # Mean Time To Acknowledge
    mtte_minutes: Optional[float] = None  # Mean Time To Engage
    mttr_minutes: Optional[float] = None  # Mean Time To Resolve


class OutOfBandContextAdd(BaseModel):
    """Payload to add a manual context entry (e.g. Slack thread, vendor note)."""

    source: str
    content: str
    timestamp: Optional[datetime] = None


class OutOfBandContextEntry(BaseModel):
    """A stored out-of-band context entry."""

    source: str
    content: str
    timestamp: Optional[datetime] = None


class PostmortemReportCreate(BaseModel):
    """Payload to trigger postmortem generation."""

    alert_id: Optional[UUID] = None
    app_id: Optional[UUID] = None


class PostmortemReportUpdate(BaseModel):
    """Fields that can be manually updated after generation."""

    title: Optional[str] = None
    timeline: Optional[List[Dict[str, Any]]] = None
    impact_summary: Optional[str] = None
    root_cause: Optional[str] = None
    contributing_factors: Optional[List[str]] = None
    remediation_actions: Optional[List[Dict[str, Any]]] = None
    action_items: Optional[List[Dict[str, Any]]] = None
    lessons_learned: Optional[str] = None
    out_of_band_context: Optional[List[Dict[str, Any]]] = None


class PostmortemReportResponse(BaseModel):
    """Full postmortem report response."""

    id: UUID
    title: str
    alert_id: Optional[UUID] = None
    app_id: Optional[UUID] = None
    status: str
    incident_start: Optional[datetime] = None
    incident_end: Optional[datetime] = None
    severity: Optional[str] = None
    timeline: List[Dict[str, Any]] = []
    impact_summary: Optional[str] = None
    root_cause: Optional[str] = None
    contributing_factors: List[str] = []
    remediation_actions: List[Dict[str, Any]] = []
    action_items: List[Dict[str, Any]] = []
    lessons_learned: Optional[str] = None
    metrics: Dict[str, Any] = {}
    generated_by: str = "ai"
    out_of_band_context: List[Dict[str, Any]] = []
    reviewed_by: Optional[UUID] = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostmortemListResponse(BaseModel):
    """Paginated list of postmortem reports."""

    items: List[PostmortemReportResponse]
    total: int
    page: int
    page_size: int
