"""
Auto-Remediation Pydantic Schemas

Request/Response models for the remediation API.
Supports IaC approach with YAML/JSON import/export.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict
import re


# =============================================================================
# ENUMS AS LITERALS
# =============================================================================

OSType = str  # "linux", "windows"
Protocol = str  # "ssh", "winrm"
TargetOS = str  # "any", "linux", "windows"
ExecutionMode = str  # "auto", "semi_auto", "manual"
ExecutionStatus = str  # "pending", "approved", "running", "success", "failed", "timeout", "cancelled", "rolled_back"
StepStatus = str  # "pending", "running", "success", "failed", "skipped", "timeout"
CircuitState = str  # "closed", "open", "half_open"
Recurrence = str  # "once", "daily", "weekly", "monthly"


# =============================================================================
# RUNBOOK STEP SCHEMAS
# =============================================================================

class RunbookStepBase(BaseModel):
    """Base schema for runbook step."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    step_type: str = Field(default="command")  # "command", "api"

    # Commands (for step_type="command")
    command_linux: Optional[str] = None
    command_windows: Optional[str] = None
    target_os: TargetOS = "any"

    # API Configuration (for step_type="api")
    api_credential_profile_id: Optional[UUID] = None  # Reference to API credential profile
    api_method: Optional[str] = None  # GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
    api_endpoint: Optional[str] = None  # endpoint path or full URL (supports Jinja2)
    api_headers_json: Optional[Dict[str, str]] = None  # custom headers
    api_body: Optional[str] = None  # request body (JSON string or Jinja2 template)
    api_body_type: str = "json"  # json, form, raw, template
    api_query_params_json: Optional[Dict[str, str]] = None  # URL query parameters
    api_expected_status_codes: List[int] = [200, 201, 202, 204]  # acceptable HTTP status codes
    api_response_extract_json: Optional[Dict[str, str]] = None  # JSONPath or regex patterns
    api_follow_redirects: bool = True
    api_retry_on_status_codes: List[int] = [408, 429, 500, 502, 503, 504]  # retry on these codes

    # Execution Options
    timeout_seconds: int = Field(default=60, ge=1, le=3600)
    requires_elevation: bool = False
    working_directory: Optional[str] = None
    environment_json: Optional[Dict[str, str]] = None

    # Error Handling
    continue_on_fail: bool = False
    retry_count: int = Field(default=0, ge=0, le=5)
    retry_delay_seconds: int = Field(default=5, ge=1, le=300)

    # Validation
    expected_exit_code: int = 0
    expected_output_pattern: Optional[str] = None
    
    # Variable Extraction
    output_variable: Optional[str] = None
    output_extract_pattern: Optional[str] = None
    
    # Conditional Execution
    run_if_variable: Optional[str] = None
    run_if_value: Optional[str] = None

    # Rollback
    rollback_command_linux: Optional[str] = None
    rollback_command_windows: Optional[str] = None

    @field_validator('expected_output_pattern')
    @classmethod
    def validate_regex(cls, v):
        if v:
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        return v

    @field_validator('step_type')
    @classmethod
    def validate_step_type(cls, v):
        if v not in ['command', 'api']:
            raise ValueError('step_type must be either "command" or "api"')
        return v

    @field_validator('api_method')
    @classmethod
    def validate_api_method(cls, v):
        if v and v not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']:
            raise ValueError('api_method must be one of: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS')
        return v

    @field_validator('api_body_type')
    @classmethod
    def validate_api_body_type(cls, v):
        if v not in ['json', 'form', 'raw', 'template']:
            raise ValueError('api_body_type must be one of: json, form, raw, template')
        return v


class RunbookStepCreate(RunbookStepBase):
    """Schema for creating a runbook step."""
    step_order: int = Field(..., ge=1)


class RunbookStepUpdate(BaseModel):
    """Schema for updating a runbook step."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    step_order: Optional[int] = Field(None, ge=1)
    step_type: Optional[str] = None
    command_linux: Optional[str] = None
    command_windows: Optional[str] = None
    target_os: Optional[TargetOS] = None
    api_credential_profile_id: Optional[UUID] = None
    api_method: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_headers_json: Optional[Dict[str, str]] = None
    api_body: Optional[str] = None
    api_body_type: Optional[str] = None
    api_query_params_json: Optional[Dict[str, str]] = None
    api_expected_status_codes: Optional[List[int]] = None
    api_response_extract_json: Optional[Dict[str, str]] = None
    timeout_seconds: Optional[int] = Field(None, ge=1, le=3600)
    requires_elevation: Optional[bool] = None
    continue_on_fail: Optional[bool] = None
    retry_count: Optional[int] = Field(None, ge=0, le=5)
    expected_exit_code: Optional[int] = None
    expected_output_pattern: Optional[str] = None
    output_variable: Optional[str] = None

    output_extract_pattern: Optional[str] = None
    run_if_variable: Optional[str] = None
    run_if_value: Optional[str] = None
    rollback_command_linux: Optional[str] = None
    rollback_command_windows: Optional[str] = None


class RunbookStepResponse(RunbookStepBase):
    """Schema for runbook step response."""
    id: UUID
    runbook_id: UUID
    step_order: int

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# RUNBOOK TRIGGER SCHEMAS
# =============================================================================

class RunbookTriggerBase(BaseModel):
    """Base schema for runbook trigger."""
    alert_name_pattern: str = "*"
    severity_pattern: str = "*"
    instance_pattern: str = "*"
    job_pattern: str = "*"
    
    label_matchers_json: Optional[Dict[str, str]] = None
    annotation_matchers_json: Optional[Dict[str, str]] = None
    
    min_duration_seconds: int = Field(default=0, ge=0)
    min_occurrences: int = Field(default=1, ge=1)
    
    priority: int = Field(default=100, ge=1, le=1000)
    enabled: bool = True


class RunbookTriggerCreate(RunbookTriggerBase):
    """Schema for creating a runbook trigger."""
    pass


class RunbookTriggerUpdate(BaseModel):
    """Schema for updating a runbook trigger."""
    alert_name_pattern: Optional[str] = None
    severity_pattern: Optional[str] = None
    instance_pattern: Optional[str] = None
    job_pattern: Optional[str] = None
    label_matchers_json: Optional[Dict[str, str]] = None
    min_duration_seconds: Optional[int] = Field(None, ge=0)
    priority: Optional[int] = Field(None, ge=1, le=1000)
    enabled: Optional[bool] = None


class RunbookTriggerResponse(RunbookTriggerBase):
    """Schema for runbook trigger response."""
    id: UUID
    runbook_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# RUNBOOK SCHEMAS
# =============================================================================

class RunbookBase(BaseModel):
    """Base schema for runbook."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    tags: List[str] = []
    
    # Execution Settings
    enabled: bool = True
    auto_execute: bool = False
    approval_required: bool = True
    approval_roles: List[str] = ["operator", "engineer", "admin"]
    approval_timeout_minutes: int = Field(default=30, ge=1, le=1440)
    
    # Safety Settings
    max_executions_per_hour: int = Field(default=5, ge=1, le=100)
    cooldown_minutes: int = Field(default=10, ge=0, le=1440)
    
    # Target Configuration
    default_server_id: Optional[UUID] = None
    target_os_filter: List[str] = ["linux", "windows"]
    target_from_alert: bool = True
    target_alert_label: str = "instance"
    
    # Notifications
    notifications_json: Optional[Dict[str, List[str]]] = None
    
    # Documentation
    documentation_url: Optional[str] = None


class RunbookCreate(RunbookBase):
    """Schema for creating a runbook."""
    steps: List[RunbookStepCreate] = []
    triggers: List[RunbookTriggerCreate] = []


class RunbookUpdate(BaseModel):
    """Schema for updating a runbook."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    enabled: Optional[bool] = None
    auto_execute: Optional[bool] = None
    approval_required: Optional[bool] = None
    approval_roles: Optional[List[str]] = None
    approval_timeout_minutes: Optional[int] = Field(None, ge=1, le=1440)
    max_executions_per_hour: Optional[int] = Field(None, ge=1, le=100)
    cooldown_minutes: Optional[int] = Field(None, ge=0, le=1440)
    default_server_id: Optional[UUID] = None
    target_os_filter: Optional[List[str]] = None
    notifications_json: Optional[Dict[str, List[str]]] = None
    documentation_url: Optional[str] = None
    
    steps: Optional[List[RunbookStepCreate]] = None
    triggers: Optional[List[RunbookTriggerCreate]] = None


class RunbookResponse(RunbookBase):
    """Schema for runbook response."""
    id: UUID
    version: int
    source: str
    source_path: Optional[str]
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    
    # Include steps and triggers
    steps: List[RunbookStepResponse] = []
    triggers: List[RunbookTriggerResponse] = []

    model_config = ConfigDict(from_attributes=True)


class RunbookListResponse(BaseModel):
    """Schema for runbook list (without steps/triggers for performance)."""
    id: UUID
    name: str
    description: Optional[str]
    category: Optional[str]
    tags: List[str]
    enabled: bool
    auto_execute: bool
    approval_required: bool
    version: int
    created_at: datetime
    updated_at: datetime
    
    # Summary counts
    steps_count: int = 0
    triggers_count: int = 0
    executions_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# EXECUTION SCHEMAS
# =============================================================================

class ExecuteRunbookRequest(BaseModel):
    """Schema for manually executing a runbook."""
    server_id: Optional[UUID] = None  # Override target server
    alert_id: Optional[UUID] = None  # Link to alert context
    dry_run: bool = False  # Test execution without running commands
    variables: Optional[Dict[str, str]] = None  # Runtime parameters
    bypass_cooldown: bool = False  # Skip cooldown check (with warning)
    bypass_blackout: bool = False  # Skip blackout check (with warning)


class ApprovalRequest(BaseModel):
    """Schema for approving/rejecting execution."""
    approved: bool
    reason: Optional[str] = None


class StepExecutionResponse(BaseModel):
    """Schema for step execution response."""
    id: UUID
    step_order: int
    step_name: str
    status: StepStatus
    command_executed: Optional[str]

    # Command execution output
    stdout: Optional[str]
    stderr: Optional[str]
    exit_code: Optional[int]

    # API execution output
    http_status_code: Optional[int]
    http_response_headers_json: Optional[Dict[str, Any]]
    http_response_body: Optional[str]
    http_request_url: Optional[str]
    http_request_method: Optional[str]
    extracted_values_json: Optional[Dict[str, Any]]

    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    retry_attempt: int
    error_type: Optional[str]
    error_message: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class RunbookExecutionResponse(BaseModel):
    """Schema for runbook execution response."""
    id: UUID
    runbook_id: UUID
    runbook_name: Optional[str] = None
    runbook_version: int
    
    alert_id: Optional[UUID]
    server_id: Optional[UUID]
    
    execution_mode: ExecutionMode
    status: ExecutionStatus
    dry_run: bool
    
    triggered_by: Optional[UUID]
    triggered_by_system: bool
    
    approval_required: bool
    approval_requested_at: Optional[datetime]
    approval_expires_at: Optional[datetime]
    approved_by: Optional[UUID]
    approved_at: Optional[datetime]
    rejection_reason: Optional[str]
    
    queued_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    result_summary: Optional[str]
    error_message: Optional[str]
    steps_total: int
    steps_completed: int
    steps_failed: int
    
    rollback_executed: bool
    
    # Include step executions
    step_executions: List[StepExecutionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ExecutionListResponse(BaseModel):
    """Schema for execution list (summary only)."""
    id: UUID
    runbook_id: UUID
    runbook_name: str
    alert_id: Optional[UUID]
    server_hostname: Optional[str]
    execution_mode: ExecutionMode
    status: ExecutionStatus
    dry_run: bool
    queued_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    steps_total: int
    steps_completed: int
    steps_failed: int

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# SAFETY MECHANISM SCHEMAS
# =============================================================================

class CircuitBreakerResponse(BaseModel):
    """Schema for circuit breaker response."""
    id: UUID
    scope: str
    scope_id: Optional[UUID]
    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_at: Optional[datetime]
    last_success_at: Optional[datetime]
    opened_at: Optional[datetime]
    closes_at: Optional[datetime]
    failure_threshold: int
    failure_window_minutes: int
    open_duration_minutes: int
    manually_opened: bool
    manually_opened_by: Optional[UUID]
    manually_opened_reason: Optional[str]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CircuitBreakerOverride(BaseModel):
    """Schema for manually opening/closing circuit breaker."""
    action: str  # "open", "close", "reset"
    reason: Optional[str] = None


class BlackoutWindowBase(BaseModel):
    """Base schema for blackout window."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    
    recurrence: Recurrence = "once"
    
    # For "once"
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # For recurring
    daily_start_time: Optional[str] = None  # "09:00"
    daily_end_time: Optional[str] = None  # "17:00"
    days_of_week: Optional[List[int]] = None  # 0=Monday
    days_of_month: Optional[List[int]] = None
    
    timezone: str = "UTC"
    
    applies_to: str = "auto_only"
    applies_to_runbook_ids: List[UUID] = []
    
    enabled: bool = True

    @field_validator('daily_start_time', 'daily_end_time')
    @classmethod
    def validate_time_format(cls, v):
        if v:
            if not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', v):
                raise ValueError("Time must be in HH:MM format (24-hour)")
        return v


class BlackoutWindowCreate(BlackoutWindowBase):
    """Schema for creating a blackout window."""
    pass


class BlackoutWindowUpdate(BaseModel):
    """Schema for updating a blackout window."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    recurrence: Optional[Recurrence] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    daily_start_time: Optional[str] = None
    daily_end_time: Optional[str] = None
    days_of_week: Optional[List[int]] = None
    timezone: Optional[str] = None
    applies_to: Optional[str] = None
    applies_to_runbook_ids: Optional[List[UUID]] = None
    enabled: Optional[bool] = None


class BlackoutWindowResponse(BlackoutWindowBase):
    """Schema for blackout window response."""
    id: UUID
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    is_active_now: bool = False

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# COMMAND SAFETY SCHEMAS
# =============================================================================

class CommandBlocklistEntry(BaseModel):
    """Schema for command blocklist entry."""
    id: UUID
    pattern: str
    pattern_type: str
    os_type: str
    description: Optional[str]
    severity: str
    enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommandBlocklistCreate(BaseModel):
    """Schema for creating blocklist entry."""
    pattern: str = Field(..., min_length=1, max_length=500)
    pattern_type: str = "regex"  # regex, contains, exact
    os_type: str = "any"
    description: Optional[str] = None
    severity: str = "critical"


class CommandValidationRequest(BaseModel):
    """Schema for validating a command."""
    command: str
    os_type: str = "linux"


class CommandValidationResponse(BaseModel):
    """Schema for command validation response."""
    is_safe: bool
    blocked_by: Optional[str] = None  # Pattern that blocked it
    blocked_reason: Optional[str] = None
    warnings: List[str] = []


# =============================================================================
# IaC IMPORT/EXPORT SCHEMAS
# =============================================================================

class RunbookYAML(BaseModel):
    """
    Schema for YAML/JSON import/export of runbooks.
    This format is designed for version control and IaC workflows.
    """
    apiVersion: str = "aiops.io/v1"
    kind: str = "Runbook"
    
    metadata: Dict[str, Any] = Field(default_factory=lambda: {
        "name": "",
        "description": "",
        "category": "",
        "tags": [],
        "documentation_url": ""
    })
    
    spec: Dict[str, Any] = Field(default_factory=lambda: {
        "execution": {
            "auto_execute": False,
            "approval_required": True,
            "approval_roles": ["operator", "engineer", "admin"],
            "approval_timeout_minutes": 30
        },
        "safety": {
            "max_executions_per_hour": 5,
            "cooldown_minutes": 10
        },
        "target": {
            "os_filter": ["linux", "windows"],
            "from_alert": True,
            "alert_label": "instance"
        },
        "notifications": {
            "on_start": [],
            "on_success": ["slack"],
            "on_failure": ["slack", "email"]
        }
    })
    
    triggers: List[Dict[str, Any]] = []
    steps: List[Dict[str, Any]] = []


class ImportRunbookRequest(BaseModel):
    """Schema for importing runbooks from YAML/JSON."""
    content: str  # YAML or JSON content
    format: str = "yaml"  # yaml, json
    overwrite: bool = False  # Overwrite existing runbook with same name


class ImportRunbookResponse(BaseModel):
    """Schema for import response."""
    success: bool
    runbook_id: Optional[UUID] = None
    runbook_name: str
    action: str  # "created", "updated", "skipped"
    errors: List[str] = []
    warnings: List[str] = []


class ExportRunbooksRequest(BaseModel):
    """Schema for exporting runbooks."""
    runbook_ids: Optional[List[UUID]] = None  # None = export all
    format: str = "yaml"  # yaml, json
    include_disabled: bool = False
