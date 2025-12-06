"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from uuid import UUID


# ============== Auth Schemas ==============

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class TokenData(BaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None


# ============== User Schemas ==============

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "operator"


class UserCreate(UserBase):
    password: str
    is_active: bool = True


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    permissions: List[str] = []

    class Config:
        from_attributes = True


# ============== LLM Provider Schemas ==============

class LLMProviderBase(BaseModel):
    name: str
    provider_type: str  # anthropic, openai, google, ollama
    model_id: str
    api_base_url: Optional[str] = None
    is_default: bool = False
    is_enabled: bool = True
    config_json: Dict[str, Any] = {"temperature": 0.3, "max_tokens": 2000}

    model_config = {
        "protected_namespaces": ()
    }


class LLMProviderCreate(LLMProviderBase):
    api_key: Optional[str] = None  # Will be encrypted before storage


class LLMProviderUpdate(BaseModel):
    name: Optional[str] = None
    model_id: Optional[str] = None
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    is_default: Optional[bool] = None
    is_enabled: Optional[bool] = None
    config_json: Optional[Dict[str, Any]] = None

    model_config = {
        "protected_namespaces": ()
    }


class LLMProviderResponse(LLMProviderBase):
    id: UUID
    has_api_key: bool = False  # Don't expose actual key
    secret_last_rotated: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============== Rule Schemas ==============

class RuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    priority: int = 100
    alert_name_pattern: str = "*"
    severity_pattern: str = "*"
    instance_pattern: str = "*"
    job_pattern: str = "*"
    action: str = "manual"  # auto_analyze, ignore, manual
    enabled: bool = True


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    alert_name_pattern: Optional[str] = None
    severity_pattern: Optional[str] = None
    instance_pattern: Optional[str] = None
    job_pattern: Optional[str] = None
    action: Optional[str] = None
    enabled: Optional[bool] = None


class RuleResponse(RuleBase):
    id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RuleTestRequest(BaseModel):
    alert_name: str
    severity: str
    instance: str
    job: str


class RuleTestResponse(BaseModel):
    matched_rule: Optional[RuleResponse] = None
    action: str
    message: str


# ============== Alert Schemas ==============

class AlertBase(BaseModel):
    alert_name: str
    severity: Optional[str] = None
    instance: Optional[str] = None
    job: Optional[str] = None
    status: str = "firing"


class AlertResponse(AlertBase):
    id: UUID
    fingerprint: Optional[str] = None
    timestamp: datetime
    labels_json: Optional[Dict[str, Any]] = None
    annotations_json: Optional[Dict[str, Any]] = None
    matched_rule_id: Optional[UUID] = None
    action_taken: Optional[str] = None
    analyzed: bool
    analyzed_at: Optional[datetime] = None
    analyzed_by: Optional[UUID] = None
    llm_provider_id: Optional[UUID] = None
    ai_analysis: Optional[str] = None
    recommendations_json: Optional[List[str]] = None
    analysis_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AnalyzeRequest(BaseModel):
    force: bool = False  # Force re-analysis even if already analyzed
    llm_provider_id: Optional[UUID] = None  # Use specific provider


class AnalysisResponse(BaseModel):
    alert_id: UUID
    analysis: str
    recommendations: List[str]
    llm_provider: str
    analyzed_at: datetime
    analysis_count: int


# ============== Webhook Schemas ==============

class AlertmanagerAlert(BaseModel):
    status: str
    labels: Dict[str, str]
    annotations: Dict[str, str] = {}
    startsAt: str
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = None


class AlertmanagerWebhook(BaseModel):
    version: str = "4"
    groupKey: str = ""
    status: str
    receiver: str = ""
    groupLabels: Dict[str, str] = {}
    commonLabels: Dict[str, str] = {}
    commonAnnotations: Dict[str, str] = {}
    externalURL: str = ""
    alerts: List[AlertmanagerAlert]


# ============== Stats Schemas ==============


class AlertTrendPoint(BaseModel):
    bucket: str
    count: int


class AlertSourceBreakdown(BaseModel):
    source: str
    count: int


class ActiveIncident(BaseModel):
    id: UUID
    alert_name: str
    severity: Optional[str] = None
    timestamp: datetime
    status: str


class StatsResponse(BaseModel):
    total_alerts: int
    analyzed_alerts: int
    pending_alerts: int
    critical_alerts: int
    warning_alerts: int
    firing_alerts: int
    resolved_alerts: int
    auto_analyzed: int
    manually_analyzed: int
    ignored: int
    total_rules: int
    enabled_rules: int
    mtta_minutes: float
    mttr_minutes: float
    remediation_success_rate: float
    severity_distribution: Dict[str, int]
    alert_trend: List[AlertTrendPoint]
    top_sources: List[AlertSourceBreakdown]
    active_incidents: List[ActiveIncident]
    health_score: int
    last_sync_time: Optional[datetime]
    connection_status: str = "online"
    time_range: str


# ============== API Credential Profile Schemas ==============

class APICredentialProfileBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    credential_type: str = Field(default="api", pattern="^(api|oauth|custom)$")
    base_url: str = Field(..., min_length=1, max_length=500)
    auth_type: str = Field(default="none", pattern="^(none|api_key|bearer|basic|oauth|custom)$")
    auth_header: Optional[str] = Field(None, max_length=100)
    username: Optional[str] = Field(None, max_length=255)
    verify_ssl: bool = True
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    default_headers: Dict[str, str] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    profile_metadata: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class APICredentialProfileCreate(APICredentialProfileBase):
    token: Optional[str] = None  # Plain text token, will be encrypted
    oauth_client_secret: Optional[str] = None  # Plain text secret, will be encrypted
    oauth_token_url: Optional[str] = Field(None, max_length=500)
    oauth_client_id: Optional[str] = Field(None, max_length=255)
    oauth_scope: Optional[str] = None


class APICredentialProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    credential_type: Optional[str] = Field(None, pattern="^(api|oauth|custom)$")
    base_url: Optional[str] = Field(None, min_length=1, max_length=500)
    auth_type: Optional[str] = Field(None, pattern="^(none|api_key|bearer|basic|oauth|custom)$")
    auth_header: Optional[str] = Field(None, max_length=100)
    username: Optional[str] = Field(None, max_length=255)
    token: Optional[str] = None  # Plain text token, will be encrypted
    verify_ssl: Optional[bool] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=300)
    default_headers: Optional[Dict[str, str]] = None
    oauth_token_url: Optional[str] = Field(None, max_length=500)
    oauth_client_id: Optional[str] = Field(None, max_length=255)
    oauth_client_secret: Optional[str] = None  # Plain text secret, will be encrypted
    oauth_scope: Optional[str] = None
    tags: Optional[List[str]] = None
    profile_metadata: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class APICredentialProfileResponse(APICredentialProfileBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    last_used_at: Optional[datetime] = None
    # Security: Never return encrypted tokens
    has_token: bool = False  # Indicates if token is set
    oauth_token_url: Optional[str] = None
    oauth_client_id: Optional[str] = None
    has_oauth_secret: bool = False  # Indicates if OAuth secret is set
    oauth_scope: Optional[str] = None

    class Config:
        from_attributes = True


# Update forward references
LoginResponse.model_rebuild()
