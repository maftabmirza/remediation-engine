"""
Pydantic schemas for AI Helper
Request/response models for API endpoints
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class SourceType(str, Enum):
    """Knowledge source types"""
    GIT_DOCS = "git_docs"
    GIT_CODE = "git_code"
    LOCAL_FILES = "local_files"
    EXTERNAL_API = "external_api"


class SourceStatus(str, Enum):
    """Knowledge source status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    ARCHIVED = "archived"


class SyncStatus(str, Enum):
    """Sync operation status"""
    PENDING = "pending"
    SYNCING = "syncing"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class AIAction(str, Enum):
    """Allowed AI actions (whitelist)"""
    SUGGEST_FORM_VALUES = "suggest_form_values"
    SEARCH_KNOWLEDGE = "search_knowledge"
    EXPLAIN_CONCEPT = "explain_concept"
    SHOW_EXAMPLE = "show_example"
    VALIDATE_INPUT = "validate_input"
    GENERATE_PREVIEW = "generate_preview"
    CHAT = "chat"


class UserAction(str, Enum):
    """User response to AI suggestion"""
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    IGNORED = "ignored"
    PENDING = "pending"
    CLICKED_LINK = "clicked_link"


class ExecutionResult(str, Enum):
    """Execution outcome"""
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"


class SessionType(str, Enum):
    """AI Helper session types"""
    GENERAL = "general"
    FORM_ASSISTANCE = "form_assistance"
    TROUBLESHOOTING = "troubleshooting"
    LEARNING = "learning"


class SessionStatus(str, Enum):
    """Session status"""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    ERROR = "error"


# ============================================================================
# KNOWLEDGE SOURCE SCHEMAS
# ============================================================================

class KnowledgeSourceBase(BaseModel):
    """Base schema for knowledge sources"""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    source_type: SourceType
    config: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    sync_schedule: Optional[str] = None
    auto_sync: bool = True


class KnowledgeSourceCreate(KnowledgeSourceBase):
    """Create knowledge source"""
    pass


class KnowledgeSourceUpdate(BaseModel):
    """Update knowledge source"""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    sync_schedule: Optional[str] = None
    auto_sync: Optional[bool] = None
    status: Optional[SourceStatus] = None


class KnowledgeSourceResponse(KnowledgeSourceBase):
    """Knowledge source response"""
    id: UUID
    tenant_id: Optional[UUID] = None
    last_sync_at: Optional[datetime] = None
    last_commit_sha: Optional[str] = None
    last_sync_status: str
    last_sync_error: Optional[str] = None
    sync_count: int
    total_documents: int
    total_chunks: int
    status: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeSyncHistoryResponse(BaseModel):
    """Sync history response"""
    id: UUID
    source_id: UUID
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    previous_commit_sha: Optional[str] = None
    new_commit_sha: Optional[str] = None
    documents_added: int
    documents_updated: int
    documents_deleted: int
    chunks_created: int
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TriggerSyncRequest(BaseModel):
    """Trigger manual sync"""
    force: bool = False


# ============================================================================
# AI HELPER INTERACTION SCHEMAS
# ============================================================================

class AIHelperQuery(BaseModel):
    """User query to AI helper"""
    query: str = Field(..., min_length=1, max_length=5000)
    session_id: Optional[UUID] = None
    page_context: Optional[Dict[str, Any]] = None


class AIHelperResponse(BaseModel):
    """AI helper response"""
    session_id: UUID
    query_id: UUID
    action: AIAction
    action_details: Dict[str, Any]
    reasoning: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    suggestions: Optional[List[str]] = None
    requires_approval: bool = True
    warning: Optional[str] = None


class AIHelperApproval(BaseModel):
    """User approval/rejection"""
    query_id: UUID
    action: UserAction
    modifications: Optional[Dict[str, Any]] = None
    feedback: Optional[str] = None


class AIHelperFeedback(BaseModel):
    """User feedback on AI response"""
    query_id: UUID
    helpful: bool
    comment: Optional[str] = None


class SolutionChoiceData(BaseModel):
    """Data about which solution was chosen"""
    solution_chosen_id: str
    solution_chosen_type: str
    solution_chosen_rank: Optional[int] = None
    user_action: str
    execution_result: Optional[str] = None
    feedback_comment: Optional[str] = None


class SolutionChoiceRequest(BaseModel):
    """Request to track solution choice"""
    audit_log_id: Optional[UUID] = None
    session_id: Optional[UUID] = None  # Chat session ID for chat page tracking
    choice_data: SolutionChoiceData


# ============================================================================
# AI AUDIT LOG SCHEMAS
# ============================================================================

class AIAuditLogCreate(BaseModel):
    """Create audit log entry"""
    user_id: UUID
    username: str
    session_id: Optional[UUID] = None
    correlation_id: Optional[UUID] = None
    user_query: str
    page_context: Optional[Dict[str, Any]] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_request: Optional[Dict[str, Any]] = None
    llm_response: Optional[Dict[str, Any]] = None
    llm_tokens_input: Optional[int] = None
    llm_tokens_output: Optional[int] = None
    llm_tokens_total: Optional[int] = None
    llm_latency_ms: Optional[int] = None
    llm_cost_usd: Optional[float] = None
    knowledge_sources_used: Optional[List[UUID]] = None
    knowledge_chunks_used: Optional[int] = None
    rag_search_time_ms: Optional[int] = None
    code_files_referenced: Optional[List[str]] = None
    code_functions_referenced: Optional[List[str]] = None
    ai_suggested_action: Optional[str] = None
    ai_action_details: Optional[Dict[str, Any]] = None
    ai_confidence_score: Optional[float] = None
    ai_reasoning: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None


class AIAuditLogUpdate(BaseModel):
    """Update audit log entry"""
    user_action: Optional[UserAction] = None
    user_modifications: Optional[Dict[str, Any]] = None
    user_feedback: Optional[str] = None
    user_feedback_comment: Optional[str] = None
    executed: Optional[bool] = None
    execution_result: Optional[ExecutionResult] = None
    execution_details: Optional[Dict[str, Any]] = None
    affected_resources: Optional[Dict[str, Any]] = None
    action_blocked: Optional[bool] = None
    block_reason: Optional[str] = None


class AIAuditLogResponse(BaseModel):
    """Audit log response"""
    id: UUID
    user_id: UUID
    username: str
    session_id: Optional[UUID] = None
    timestamp: datetime
    user_query: str
    page_context: Optional[Dict[str, Any]] = None
    ai_suggested_action: Optional[str] = None
    ai_action_details: Optional[Dict[str, Any]] = None
    user_action: Optional[str] = None
    executed: bool
    execution_result: Optional[str] = None
    action_blocked: bool
    block_reason: Optional[str] = None
    llm_tokens_total: Optional[int] = None
    llm_cost_usd: Optional[float] = None
    total_duration_ms: Optional[int] = None

    class Config:
        from_attributes = True


# ============================================================================
# AI HELPER SESSION SCHEMAS
# ============================================================================

class AIHelperSessionCreate(BaseModel):
    """Create AI helper session"""
    session_type: SessionType = SessionType.GENERAL
    context: Optional[Dict[str, Any]] = None


class AIHelperSessionResponse(BaseModel):
    """AI helper session response"""
    id: UUID
    user_id: UUID
    session_type: str
    context: Optional[Dict[str, Any]] = None
    status: str
    total_queries: int
    total_tokens_used: int
    total_cost_usd: float
    started_at: datetime
    last_activity_at: datetime
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================================
# AI HELPER CONFIG SCHEMAS
# ============================================================================

class AIHelperConfigResponse(BaseModel):
    """AI helper configuration response"""
    config_key: str
    config_value: Dict[str, Any]
    description: Optional[str] = None
    enabled: bool

    class Config:
        from_attributes = True


class AIHelperConfigUpdate(BaseModel):
    """Update AI helper configuration"""
    config_value: Dict[str, Any]
    enabled: Optional[bool] = None


# ============================================================================
# ANALYTICS SCHEMAS
# ============================================================================

class AIHelperAnalytics(BaseModel):
    """AI helper usage analytics"""
    total_queries: int
    total_sessions: int
    total_tokens_used: int
    total_cost_usd: float
    avg_response_time_ms: float
    approval_rate: float
    rejection_rate: float
    modification_rate: float
    most_common_actions: List[Dict[str, Any]]
    top_users: List[Dict[str, Any]]
    error_rate: float
    blocked_actions_count: int


class UserAIHelperStats(BaseModel):
    """User-specific AI helper statistics"""
    user_id: UUID
    username: str
    total_queries: int
    total_sessions: int
    avg_session_queries: float
    total_tokens_used: int
    total_cost_usd: float
    approval_rate: float
    most_used_actions: List[str]
    last_activity_at: Optional[datetime] = None
