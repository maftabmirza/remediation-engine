"""
Pydantic schemas for PII detection API.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# Detection Request/Response Models
class DetectionRequest(BaseModel):
    """Request to detect PII/secrets in text."""
    text: str = Field(..., description="Text to scan for PII/secrets")
    source_type: str = Field(..., description="Type of source: runbook_output, llm_response, alert, etc.")
    source_id: Optional[str] = Field(None, description="ID of the source record")
    engines: Optional[List[str]] = Field(None, description="Engines to use: presidio, detect_secrets. Defaults to both")
    entity_types: Optional[List[str]] = Field(None, description="Specific entity types to detect. Defaults to all enabled")


class DetectionResult(BaseModel):
    """Individual detection result."""
    entity_type: str
    engine: str
    value: str
    start: int
    end: int
    confidence: float
    context: str


class DetectionResponse(BaseModel):
    """Response from detection endpoint."""
    detections: List[DetectionResult]
    detection_count: int
    processing_time_ms: int


# Redaction Models
class RedactionRequest(BaseModel):
    """Request to redact PII/secrets from text."""
    text: str
    redaction_type: str = Field("mask", description="Type: mask, hash, remove, tag")
    mask_char: str = Field("*", max_length=1)
    preserve_length: bool = False


class RedactionItem(BaseModel):
    """Single redaction item with mapping for de-anonymization."""
    placeholder: str  # e.g., "[EMAIL_ADDRESS]"
    original: str     # e.g., "john@example.com"
    entity_type: str
    start: int
    end: int


class RedactionResponse(BaseModel):
    """Response from redaction endpoint."""
    original_length: int
    redacted_text: str
    redactions_applied: int
    detections: List[DetectionResult]
    items: List[RedactionItem] = []  # Mapping for de-anonymization


# Configuration Models
class EntityConfig(BaseModel):
    """Configuration for a single entity type."""
    entity_type: str
    enabled: bool
    threshold: float = Field(ge=0.0, le=1.0)
    redaction_type: str


class PresidioConfig(BaseModel):
    """Presidio engine configuration."""
    enabled: bool
    entities: List[EntityConfig]


class PluginConfig(BaseModel):
    """Configuration for a detect-secrets plugin."""
    plugin_name: str
    enabled: bool
    settings: Dict[str, Any] = Field(default_factory=dict)


class DetectSecretsConfig(BaseModel):
    """detect-secrets engine configuration."""
    enabled: bool
    plugins: List[PluginConfig]


class GlobalSettings(BaseModel):
    """Global PII detection settings."""
    log_detections: bool = True
    auto_redact: bool = True
    default_redaction_type: str = "mask"


class PIIConfigResponse(BaseModel):
    """Complete PII configuration."""
    presidio: PresidioConfig
    detect_secrets: DetectSecretsConfig
    global_settings: GlobalSettings


class PIIConfigUpdate(BaseModel):
    """Partial update to PII configuration."""
    presidio: Optional[PresidioConfig] = None
    detect_secrets: Optional[DetectSecretsConfig] = None
    global_settings: Optional[GlobalSettings] = None


# Log Models
class DetectionLogResponse(BaseModel):
    """Single detection log entry."""
    id: UUID
    detected_at: datetime
    entity_type: str
    detection_engine: str
    confidence_score: float
    source_type: str
    source_id: Optional[UUID]
    context_snippet: Optional[str]
    was_redacted: bool
    
    class Config:
        from_attributes = True


class DetectionLogListResponse(BaseModel):
    """Paginated list of detection logs."""
    logs: List[DetectionLogResponse]
    total: int
    page: int
    limit: int
    pages: int


class DetectionLogQuery(BaseModel):
    """Query parameters for log search."""
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=1000)
    entity_type: Optional[str] = None
    engine: Optional[str] = None
    source_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    q: Optional[str] = None


class DetectionLogSearchResponse(BaseModel):
    """Search results for detection logs."""
    results: List[DetectionLogResponse]
    total: int
    query: str
    filters_applied: Dict[str, Any]


class DetectionStatsResponse(BaseModel):
    """Statistics about detections."""
    period: str
    total_detections: int
    by_entity_type: Dict[str, int]
    by_engine: Dict[str, int]
    by_source: Dict[str, int]
    trend: List[Dict[str, Any]]


class DetectionLogDetailResponse(BaseModel):
    """Detailed view of a single detection log."""
    id: UUID
    detected_at: datetime
    entity_type: str
    detection_engine: str
    confidence_score: float
    source_type: str
    source_id: Optional[UUID]
    context_snippet: Optional[str]
    position_start: int
    position_end: int
    was_redacted: bool
    redaction_type: Optional[str]
    original_hash: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Test Models
class TestDetectionRequest(BaseModel):
    """Request to test detection on sample text."""
    text: str
    engines: List[str] = Field(default=["presidio", "detect_secrets"])


class EngineResults(BaseModel):
    """Results from a single engine."""
    detections: int
    processing_time_ms: int


class TestDetectionResponse(BaseModel):
    """Response from test endpoint."""
    detections: List[DetectionResult]
    redacted_preview: str
    engine_results: Dict[str, EngineResults]


# Entity/Plugin List Models
class EntityInfo(BaseModel):
    """Information about an entity type."""
    name: str
    description: str
    built_in: bool


class EntityListResponse(BaseModel):
    """List of available entity types."""
    presidio_entities: List[EntityInfo]


class PluginInfo(BaseModel):
    """Information about a plugin."""
    name: str
    description: str
    configurable: bool


class PluginListResponse(BaseModel):
    """List of available plugins."""
    detect_secrets_plugins: List[PluginInfo]


# False Positive Feedback Models
class FalsePositiveFeedbackRequest(BaseModel):
    """Request to report a false positive PII detection."""
    detected_text: str = Field(..., max_length=500, description="The text that was incorrectly flagged")
    detected_entity_type: str = Field(..., description="Entity type that was detected")
    detection_engine: str = Field(..., description="Engine that made detection")
    session_id: Optional[str] = Field(None, description="Agent session ID for context")
    agent_mode: Optional[str] = Field(None, description="alert/revive/troubleshoot")
    detection_log_id: Optional[UUID] = Field(None, description="Reference to detection log entry")
    user_comment: Optional[str] = Field(None, max_length=1000, description="Optional reason")
    original_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Original confidence score")


class FalsePositiveFeedbackResponse(BaseModel):
    """Response after submitting false positive feedback."""
    id: UUID
    detected_text: str
    detected_entity_type: str
    whitelisted: bool
    review_status: str
    reported_at: datetime
    message: str = Field(default="Feedback submitted successfully. This text will no longer be flagged.")
    
    class Config:
        from_attributes = True


class FalsePositiveFeedbackDetail(BaseModel):
    """Detailed view of false positive feedback."""
    id: UUID
    detected_text: str
    detected_entity_type: str
    detection_engine: str
    original_confidence: Optional[float]
    user_id: UUID
    session_id: Optional[str]
    agent_mode: Optional[str]
    reported_at: datetime
    user_comment: Optional[str]
    whitelisted: bool
    whitelisted_at: datetime
    whitelist_scope: str
    review_status: str
    reviewed_by: Optional[UUID]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FalsePositiveFeedbackListResponse(BaseModel):
    """Paginated list of false positive feedback."""
    items: List[FalsePositiveFeedbackDetail]
    total: int
    page: int
    limit: int
    pages: int


class WhitelistEntry(BaseModel):
    """Single whitelist entry."""
    id: UUID
    text: str
    entity_type: str
    scope: str
    added_at: datetime
    added_by: UUID
    reported_by: Optional[str] = None
    session_id: Optional[str] = None
    active: bool


class WhitelistResponse(BaseModel):
    """List of whitelisted items."""
    items: List[WhitelistEntry]
    total: int


class WhitelistUpdateRequest(BaseModel):
    """Request to update whitelist entry."""
    whitelisted: bool = Field(..., description="Enable or disable this whitelist entry")
    review_notes: Optional[str] = Field(None, description="Admin notes")


class PIIHighlightInfo(BaseModel):
    """Information about PII detection for UI highlighting."""
    detection_id: Optional[UUID] = Field(None, description="Reference to detection log")
    text: str = Field(..., description="The detected text")
    entity_type: str = Field(..., description="Type of PII detected")
    start_pos: int = Field(..., ge=0, description="Start position in response")
    end_pos: int = Field(..., ge=0, description="End position in response")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    can_report: bool = Field(default=True, description="User can report as false positive")
    already_whitelisted: bool = Field(default=False, description="Already in whitelist")
