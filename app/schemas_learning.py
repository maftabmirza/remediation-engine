"""
Learning System Pydantic Schemas
Request/response models for feedback and effectiveness APIs
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# ============================================================================
# Feedback Schemas
# ============================================================================

class FeedbackCreate(BaseModel):
    """Request schema for creating analysis feedback"""
    helpful: Optional[bool] = None
    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating from 1-5 stars")
    accuracy: Optional[str] = Field(None, description="accurate, partially_accurate, or inaccurate")
    what_was_missing: Optional[str] = None
    what_actually_worked: Optional[str] = None
    
    @field_validator('accuracy')
    @classmethod
    def validate_accuracy(cls, v):
        if v is not None and v not in ['accurate', 'partially_accurate', 'inaccurate']:
            raise ValueError("accuracy must be one of: accurate, partially_accurate, inaccurate")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "helpful": True,
                "rating": 4,
                "accuracy": "partially_accurate",
                "what_was_missing": "Didn't mention connection pool settings",
                "what_actually_worked": "Increased pool size to 100"
            }
        }
    )


class FeedbackResponse(BaseModel):
    """Response schema for analysis feedback"""
    id: UUID
    alert_id: UUID
    user_id: Optional[UUID]
    helpful: Optional[bool]
    rating: Optional[int]
    accuracy: Optional[str]
    what_was_missing: Optional[str]
    what_actually_worked: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Execution Outcome Schemas
# ============================================================================

class ExecutionOutcomeCreate(BaseModel):
    """Request schema for creating execution outcome"""
    resolved_issue: Optional[bool] = None
    resolution_type: Optional[str] = Field(None, description="full, partial, no_effect, or made_worse")
    time_to_resolution_minutes: Optional[int] = Field(None, ge=0, description="Time to resolution in minutes")
    recommendation_followed: Optional[bool] = None
    manual_steps_taken: Optional[str] = None
    improvement_suggestion: Optional[str] = None
    
    @field_validator('resolution_type')
    @classmethod
    def validate_resolution_type(cls, v):
        if v is not None and v not in ['full', 'partial', 'no_effect', 'made_worse']:
            raise ValueError("resolution_type must be one of: full, partial, no_effect, made_worse")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "resolved_issue": True,
                "resolution_type": "full",
                "time_to_resolution_minutes": 8,
                "recommendation_followed": True,
                "improvement_suggestion": "Add step to check pool size first"
            }
        }
    )


class ExecutionOutcomeResponse(BaseModel):
    """Response schema for execution outcome"""
    id: UUID
    execution_id: UUID
    alert_id: Optional[UUID]
    user_id: Optional[UUID]
    resolved_issue: Optional[bool]
    resolution_type: Optional[str]
    time_to_resolution_minutes: Optional[int]
    recommendation_followed: Optional[bool]
    manual_steps_taken: Optional[str]
    improvement_suggestion: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Effectiveness Schemas
# ============================================================================

class RunbookEffectivenessMetrics(BaseModel):
    """Metrics for runbook effectiveness"""
    success_rate: float = Field(description="Percentage of successful executions")
    avg_resolution_minutes: float = Field(description="Average time to resolution")
    total_executions: int = Field(description="Total number of executions")
    positive_feedback_rate: float = Field(description="Percentage of positive feedback")
    recommendation_followed_rate: float = Field(description="Percentage where recommendation was followed")


class AlertTypeBreakdown(BaseModel):
    """Effectiveness breakdown by alert type"""
    alert_type: str
    success_rate: float
    count: int
    avg_resolution_minutes: Optional[float]


class RunbookEffectiveness(BaseModel):
    """Response schema for runbook effectiveness"""
    runbook_id: UUID
    runbook_name: str
    overall_score: float = Field(description="Overall effectiveness score (0-100)")
    metrics: RunbookEffectivenessMetrics
    by_alert_type: List[AlertTypeBreakdown] = []
    improvement_suggestions: List[str] = []
    last_updated: datetime


# ============================================================================
# Similar Incident Schemas
# ============================================================================

class ResolutionInfo(BaseModel):
    """Information about how an incident was resolved"""
    method: str = Field(description="runbook, manual, or auto")
    runbook_id: Optional[UUID] = None
    runbook_name: Optional[str] = None
    success: bool
    time_minutes: Optional[int]


class SimilarIncident(BaseModel):
    """A similar historical incident"""
    alert_id: UUID
    alert_name: str
    similarity_score: float = Field(ge=0.0, le=1.0, description="Cosine similarity score")
    occurred_at: datetime
    severity: Optional[str]
    instance: Optional[str]
    resolution: Optional[ResolutionInfo]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "alert_id": "550e8400-e29b-41d4-a716-446655440000",
                "alert_name": "HighCPU",
                "similarity_score": 0.94,
                "occurred_at": "2024-12-10T10:00:00Z",
                "severity": "critical",
                "instance": "web-server-01",
                "resolution": {
                    "method": "runbook",
                    "runbook_name": "Restart Service",
                    "success": True,
                    "time_minutes": 5
                }
            }
        }
    )


class SimilarIncidentsResponse(BaseModel):
    """Response schema for similar incidents query"""
    alert_id: UUID
    similar_incidents: List[SimilarIncident]
    total_found: int


# ============================================================================
# Embedding Generation Schemas
# ============================================================================

class EmbeddingGenerationRequest(BaseModel):
    """Request to generate embeddings for alerts"""
    limit: Optional[int] = Field(100, description="Maximum number of alerts to process")
    force_regenerate: bool = Field(False, description="Regenerate embeddings even if they exist")


class EmbeddingGenerationResponse(BaseModel):
    """Response from embedding generation task"""
    task_id: str
    status: str
    alerts_to_process: int
    message: str
