"""
Troubleshooting Schemas
Pydantic models for correlation and troubleshooting API
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class AlertSummary(BaseModel):
    """Brief summary of an alert in a correlation"""
    id: UUID
    alert_name: str
    severity: str
    status: str
    timestamp: datetime


class AlertCorrelationResponse(BaseModel):
    """Response schema for an alert correlation group"""
    id: UUID
    summary: str
    root_cause_analysis: Optional[str]
    status: str
    confidence_score: Optional[float]
    created_at: datetime
    updated_at: datetime
    alerts: List[AlertSummary] = []

    class Config:
        from_attributes = True


class RootCauseAnalysis(BaseModel):
    """Analysis result for root cause"""
    root_cause: str
    confidence: float
    reasoning: List[str]
    related_alerts: List[UUID]
    recommended_actions: List[str]


class InvestigationStep(BaseModel):
    """Single step in an investigation path"""
    step_number: int
    action: str
    description: str
    component: Optional[str]
    command_to_run: Optional[str] = None


class InvestigationPath(BaseModel):
    """Full investigation path"""
    alert_id: UUID
    steps: List[InvestigationStep]
    estimated_time_minutes: int


class FailurePatternResponse(BaseModel):
    """Response schema for failure pattern"""
    id: UUID
    root_cause_type: str
    description: str
    confidence_score: float
    occurrence_count: int
    last_seen_at: datetime
    
    class Config:
        from_attributes = True
