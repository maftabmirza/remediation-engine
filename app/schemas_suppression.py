"""
Pydantic schemas for Alert Suppression Rules.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class AlertSuppressionRuleBase(BaseModel):
    """Fields shared between create, update, and response schemas."""

    name: str = Field(..., max_length=200, description="Human-readable rule name")
    rule_type: str = Field(
        ...,
        max_length=20,
        description="One of: time_based, label_based, service_based, maintenance",
    )
    matchers: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Dict of label name → regex pattern. "
            'Example: {"alertname": ".*CPU.*", "severity": "warning"}'
        ),
    )
    app_id: Optional[UUID] = Field(None, description="Restrict rule to this application")
    starts_at: datetime = Field(..., description="Window start (UTC)")
    ends_at: Optional[datetime] = Field(None, description="Window end (UTC). NULL = permanent")
    grace_period_minutes: int = Field(
        5, ge=0, description="Minutes to continue suppression after window ends"
    )
    is_active: bool = Field(True, description="Whether the rule is currently active")


# ---------------------------------------------------------------------------
# Create / Update
# ---------------------------------------------------------------------------


class AlertSuppressionRuleCreate(AlertSuppressionRuleBase):
    """Request body for POST /api/alert-suppression/."""


class AlertSuppressionRuleUpdate(BaseModel):
    """Request body for PUT /api/alert-suppression/{id}. All fields optional."""

    name: Optional[str] = Field(None, max_length=200)
    rule_type: Optional[str] = Field(None, max_length=20)
    matchers: Optional[Dict[str, Any]] = None
    app_id: Optional[UUID] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    grace_period_minutes: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class AlertSuppressionRuleResponse(AlertSuppressionRuleBase):
    """Response schema for a single suppression rule."""

    id: UUID
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertSuppressionRuleListResponse(BaseModel):
    """Paginated list of suppression rules."""

    rules: List[AlertSuppressionRuleResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Dry-run check
# ---------------------------------------------------------------------------


class SuppressionCheckRequest(BaseModel):
    """Request body for POST /api/alert-suppression/check (dry-run)."""

    labels: Dict[str, Any] = Field(
        ..., description="Alert labels to test against active suppression rules"
    )
    app_id: Optional[UUID] = Field(None, description="Optional application ID")


class SuppressionCheckResponse(BaseModel):
    """Result of the dry-run suppression check."""

    suppressed: bool
    matched_rule: Optional[AlertSuppressionRuleResponse] = None
