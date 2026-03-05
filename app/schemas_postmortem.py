"""
Post-Incident Postmortem Pydantic Schemas

Request/response models for postmortem report generation and management.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Nested value objects
# ---------------------------------------------------------------------------

class TimelineEntry(BaseModel):
    """Single event in the incident timeline."""

    timestamp: datetime
    event: str
    source: str
    manual: bool = False

    model_config = ConfigDict(from_attributes=True)


class RemediationAction(BaseModel):
    """Record of a remediation action taken during the incident."""

    action: str
    runbook_id: Optional[UUID] = None
    outcome: Optional[str] = None
    duration_minutes: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ActionItem(BaseModel):
    """Follow-up task to be completed after the incident."""

    description: str
    owner: Optional[str] = None
    due_date: Optional[date] = None
    status: str = Field(default="open", description="open | in_progress | done")

    model_config = ConfigDict(from_attributes=True)


class IncidentMetricsSummary(BaseModel):
    """Key incident timing metrics in minutes."""

    mttd_minutes: Optional[float] = Field(None, description="Mean time to detect")
    mtta_minutes: Optional[float] = Field(None, description="Mean time to acknowledge")
    mtte_minutes: Optional[float] = Field(None, description="Mean time to engage")
    mttr_minutes: Optional[float] = Field(None, description="Mean time to resolve")

    model_config = ConfigDict(from_attributes=True)


class OutOfBandContextEntry(BaseModel):
    """Manual context entry added from external sources (Slack, vendor, customer)."""

    source: str = Field(..., description="e.g. 'slack', 'vendor', 'customer', 'manual'")
    content: str
    timestamp: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class PostmortemReportCreate(BaseModel):
    """Request body to trigger AI postmortem generation for an alert."""

    alert_id: Optional[UUID] = None
    app_id: Optional[UUID] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"alert_id": "123e4567-e89b-12d3-a456-426614174000"}
        }
    )


class PostmortemReportUpdate(BaseModel):
    """
    Request body for editing an existing postmortem.

    All fields are optional so callers only need to send changed fields.
    """

    title: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = Field(
        None, description="draft | in_review | published"
    )
    severity: Optional[str] = None
    incident_start: Optional[datetime] = None
    incident_end: Optional[datetime] = None
    impact_summary: Optional[str] = None
    root_cause: Optional[str] = None
    contributing_factors: Optional[List[str]] = None
    timeline: Optional[List[TimelineEntry]] = None
    remediation_actions: Optional[List[RemediationAction]] = None
    action_items: Optional[List[ActionItem]] = None
    lessons_learned: Optional[str] = None
    out_of_band_context: Optional[List[OutOfBandContextEntry]] = None
    metrics: Optional[IncidentMetricsSummary] = None


class OutOfBandContextAdd(BaseModel):
    """Request body for adding a single out-of-band context entry."""

    source: str = Field(..., description="e.g. 'slack', 'vendor', 'customer'")
    content: str
    timestamp: Optional[datetime] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source": "slack",
                "content": "Customer reported service degradation at 14:03 UTC",
                "timestamp": "2026-03-05T14:03:00Z",
            }
        }
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class PostmortemReportResponse(BaseModel):
    """Full postmortem report returned by the API."""

    id: UUID
    title: str
    status: str
    severity: Optional[str] = None
    generated_by: str
    incident_start: Optional[datetime] = None
    incident_end: Optional[datetime] = None
    alert_id: Optional[UUID] = None
    app_id: Optional[UUID] = None
    impact_summary: Optional[str] = None
    root_cause: Optional[str] = None
    contributing_factors: List[str] = Field(default_factory=list)
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    remediation_actions: List[Dict[str, Any]] = Field(default_factory=list)
    action_items: List[Dict[str, Any]] = Field(default_factory=list)
    lessons_learned: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    out_of_band_context: List[Dict[str, Any]] = Field(default_factory=list)
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

    model_config = ConfigDict(from_attributes=True)
