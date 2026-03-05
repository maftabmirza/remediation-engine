"""
Schemas for AI-Powered Runbook Auto-Generation (Feature B2).

Provides request/response models for generating runbook drafts from
successful agent troubleshooting sessions.
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GenerationCandidate(BaseModel):
    """A cluster of similar successful sessions that can be turned into a runbook."""

    session_ids: List[UUID] = Field(..., description="Sessions in this cluster")
    session_count: int = Field(..., description="Number of sessions in this cluster")
    goal_summary: str = Field(..., description="Inferred goal from session goals")
    app_id: Optional[UUID] = Field(None, description="Application associated with the sessions")
    success_rate: float = Field(..., description="Fraction of sessions that resolved successfully (0-1)")
    avg_resolution_minutes: Optional[float] = Field(
        None, description="Average time to resolution in minutes"
    )
    representative_commands: List[str] = Field(
        default_factory=list,
        description="Sample commands extracted from the cluster",
    )


class GenerationCandidateListResponse(BaseModel):
    """Paginated list of generation candidates."""

    items: List[GenerationCandidate]
    total: int


class GenerateRunbookRequest(BaseModel):
    """Request body to generate a runbook from selected sessions."""

    session_ids: List[UUID] = Field(..., min_length=1, description="Must be ≥ 1 session")
    runbook_name: Optional[str] = Field(None, description="Override auto-generated name")
    app_id: Optional[UUID] = Field(None, description="Application to associate the runbook with")


class GeneratedStepPreview(BaseModel):
    """Preview of a single generated runbook step."""

    step_number: int
    name: str
    step_type: str = Field(
        ..., description="One of: command, api, conditional, rollback"
    )
    command_template: str = Field(
        ..., description="Command with Jinja2 {{ variable }} placeholders"
    )
    variables_required: List[str] = Field(
        default_factory=list, description="Variable names extracted from the template"
    )
    is_idempotent: Optional[bool] = Field(
        None, description="None = unknown, True/False from LLM analysis"
    )
    requires_human_review: bool = Field(
        ..., description="True if a non-idempotent pattern was detected"
    )


class RunbookDraftResponse(BaseModel):
    """Full response after generating a runbook draft."""

    runbook_id: UUID
    name: str
    description: str
    source: str = Field(..., description="Always 'auto_generated'")
    auto_trigger_enabled: bool = Field(
        ..., description="Always False until approved"
    )
    steps: List[GeneratedStepPreview]
    variables: List[str] = Field(
        default_factory=list, description="All unique variables across steps"
    )
    requires_review_reasons: List[str] = Field(
        default_factory=list, description="Why human review is needed"
    )
    session_count: int = Field(..., description="Sessions this was generated from")
