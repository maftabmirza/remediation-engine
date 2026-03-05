"""
Confidence Score Pydantic Schemas

Response models for the remediation confidence scoring feature.
"""
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class SampleOutcome(BaseModel):
    """Represents the outcome of a single similar historical incident."""

    alert_id: UUID
    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score (0-1)")
    outcome: str = Field(..., description="success | failure | partial")
    resolution_time_minutes: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ConfidenceScore(BaseModel):
    """
    Confidence score for a runbook execution against a specific alert.

    Computed from historical performance on similar alerts.  When insufficient
    data is available, the score falls back to the runbook's overall
    effectiveness rating.
    """

    score: float = Field(..., ge=0.0, le=100.0, description="Confidence percentage 0–100")
    explanation: str = Field(..., description="Human-readable reason for the score")
    similar_count: int = Field(..., ge=0, description="Number of similar past alerts found")
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Weighted success rate 0–1")
    avg_resolution_minutes: Optional[float] = None
    sample_outcomes: List[SampleOutcome] = Field(default_factory=list)
    confidence_level: str = Field(
        ...,
        description="high (≥70) | medium (40-69) | low (<40) | insufficient_data",
    )

    model_config = ConfigDict(from_attributes=True)
