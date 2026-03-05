"""
Confidence Score Schemas
Pydantic schemas for remediation confidence scoring.
"""
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SampleOutcome(BaseModel):
    """A single historical outcome sample used in confidence calculation."""

    alert_id: UUID
    similarity: float = Field(..., ge=0.0, le=1.0)
    outcome: str  # "success" | "failure" | "partial"
    resolution_time_minutes: Optional[float] = None


class ConfidenceScore(BaseModel):
    """Confidence score for a runbook execution on a given alert."""

    score: float = Field(..., ge=0.0, le=100.0)
    explanation: str
    similar_count: int = Field(..., ge=0)
    success_rate: float = Field(..., ge=0.0, le=1.0)
    avg_resolution_minutes: Optional[float] = None
    sample_outcomes: List[SampleOutcome] = []
    confidence_level: str  # "high" (≥70), "medium" (40-69), "low" (<40), "insufficient_data"
