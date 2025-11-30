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
    role: str = "user"


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: UUID
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

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


# Update forward references
LoginResponse.model_rebuild()
