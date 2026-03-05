"""
Schemas for Runbook Auto-Generation API (Feature B2).
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GenerationCandidate(BaseModel):
    """A cluster of similar successful sessions that can be used to generate a runbook."""

    session_ids: List[UUID] = Field(description="Sessions in this cluster")
    session_count: int
    goal_summary: str = Field(description="Inferred from session goals")
    app_id: Optional[UUID] = None
    success_rate: float
    avg_resolution_minutes: Optional[float] = None
    representative_commands: List[str] = Field(
        default_factory=list,
        description="Sample extracted commands from the sessions",
    )


class GenerationCandidateListResponse(BaseModel):
    """Paginated list of generation candidates."""

    items: List[GenerationCandidate]
    total: int


class GenerateRunbookRequest(BaseModel):
    """Request body for generating a runbook from past sessions."""

    session_ids: List[UUID] = Field(min_length=1, description="Must be ≥ 1 session")
    runbook_name: Optional[str] = Field(None, description="Override auto-generated name")
    app_id: Optional[UUID] = None


class GeneratedStepPreview(BaseModel):
    """A single step in the generated runbook draft."""

    step_number: int
    name: str
    step_type: str = Field(description="command, api, conditional, or rollback")
    command_template: str = Field(description="May contain Jinja2 {{ variable }} placeholders")
    variables_required: List[str] = Field(
        default_factory=list,
        description="Variable names extracted from the template",
    )
    is_idempotent: Optional[bool] = Field(
        None,
        description="None = unknown, True/False from LLM analysis",
    )
    requires_human_review: bool = Field(
        description="True if non-idempotent pattern detected",
    )


class RunbookDraftResponse(BaseModel):
    """Response schema for a newly generated runbook draft."""

    runbook_id: UUID
    name: str
    description: str
    source: str = Field(description="Always 'auto_generated'")
    auto_trigger_enabled: bool = Field(description="Always False until approved")
    steps: List[GeneratedStepPreview]
    variables: List[str] = Field(description="All unique variables across steps")
    requires_review_reasons: List[str] = Field(
        description="Why human review is needed",
    )
    session_count: int = Field(description="Sessions this was generated from")
