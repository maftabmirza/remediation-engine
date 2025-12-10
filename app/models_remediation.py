"""
Auto-Remediation Models

Enterprise-grade runbook execution and safety mechanism models.
Follows IaC principles - runbooks can be defined as code/YAML and imported.
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Column, String, Boolean, Integer, Text, ForeignKey, 
    DateTime, JSON, CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


# =============================================================================
# ENUMS (stored as strings for flexibility)
# =============================================================================
# OSType: "linux", "windows"
# Protocol: "ssh", "winrm"
# WinRMTransport: "kerberos", "ntlm", "certificate"
# TargetOS: "any", "linux", "windows"
# ExecutionMode: "auto", "semi_auto", "manual"
# ExecutionStatus: "pending", "approved", "running", "success", "failed", 
#                  "timeout", "cancelled", "rolled_back"
# StepStatus: "pending", "running", "success", "failed", "skipped", "timeout"
# CircuitState: "closed", "open", "half_open"
# Recurrence: "once", "daily", "weekly", "monthly"


# =============================================================================
# RUNBOOK DEFINITION
# =============================================================================

class Runbook(Base):
    """
    Runbook definition - a reusable remediation procedure.
    
    Runbooks can be:
    - Created via UI
    - Imported from YAML/JSON (IaC approach)
    - Version controlled with Git integration
    """
    __tablename__ = "runbooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic Info
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True, index=True)  # e.g., "web-services", "database", "infrastructure"
    tags = Column(ARRAY(String), default=[])  # For filtering/search
    
    # Execution Settings
    enabled = Column(Boolean, default=True, index=True)
    auto_execute = Column(Boolean, default=False, index=True)  # Full auto mode
    approval_required = Column(Boolean, default=True)  # Semi-auto requires approval
    approval_roles = Column(ARRAY(String), default=["operator", "engineer", "admin"])
    approval_timeout_minutes = Column(Integer, default=30)
    
    # Safety Settings
    max_executions_per_hour = Column(Integer, default=5)
    cooldown_minutes = Column(Integer, default=10)  # Min time between executions on same target
    
    # Target Configuration
    default_server_id = Column(UUID(as_uuid=True), ForeignKey("server_credentials.id"), nullable=True)
    target_os_filter = Column(ARRAY(String), default=["linux", "windows"])  # Which OS this runbook supports
    target_from_alert = Column(Boolean, default=True)  # Extract target from alert labels
    target_alert_label = Column(String(50), default="instance")  # Which label contains the target
    
    # Versioning (IaC support)
    version = Column(Integer, default=1)
    source = Column(String(20), default="ui")  # "ui", "yaml", "git"
    source_path = Column(String(255), nullable=True)  # Path to YAML file or Git repo
    checksum = Column(String(64), nullable=True)  # SHA256 of source for change detection
    
    # Notifications (JSON for flexibility)
    notifications_json = Column(JSON, default={
        "on_start": [],
        "on_success": ["slack"],
        "on_failure": ["slack", "email"]
    })
    
    # Documentation
    documentation_url = Column(String(500), nullable=True)
    
    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    steps = relationship("RunbookStep", back_populates="runbook", cascade="all, delete-orphan", order_by="RunbookStep.step_order")
    triggers = relationship("RunbookTrigger", back_populates="runbook", cascade="all, delete-orphan")
    executions = relationship("RunbookExecution", back_populates="runbook")
    schedules = relationship("ScheduledJob", back_populates="runbook", cascade="all, delete-orphan")
    default_server = relationship("ServerCredential")
    created_by_user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index("idx_runbooks_enabled_auto", "enabled", "auto_execute"),
        Index("idx_runbooks_category", "category"),
    )


class RunbookStep(Base):
    """
    Individual step within a runbook.
    Steps can execute commands (Linux/Windows) or API calls.
    """
    __tablename__ = "runbook_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runbook_id = Column(UUID(as_uuid=True), ForeignKey("runbooks.id", ondelete="CASCADE"), nullable=False)

    # Step Definition
    step_order = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    step_type = Column(String(20), default="command")  # "command", "api"

    # Commands (platform-specific) - for step_type="command"
    command_linux = Column(Text, nullable=True)  # Bash command
    command_windows = Column(Text, nullable=True)  # PowerShell command
    target_os = Column(String(10), default="any")  # "any", "linux", "windows"

    # API Configuration - for step_type="api"
    api_credential_profile_id = Column(UUID(as_uuid=True), ForeignKey("api_credential_profiles.id", ondelete="SET NULL"), nullable=True)  # Reference to API credentials
    api_method = Column(String(10), nullable=True)  # GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
    api_endpoint = Column(Text, nullable=True)  # endpoint path or full URL (supports Jinja2)
    api_headers_json = Column(JSON, nullable=True)  # custom headers for this request
    api_body = Column(Text, nullable=True)  # request body (JSON string or Jinja2 template)
    api_body_type = Column(String(30), default="json")  # json, form, raw, template
    api_query_params_json = Column(JSON, nullable=True)  # URL query parameters
    api_expected_status_codes = Column(ARRAY(Integer), default=[200, 201, 202, 204])  # acceptable HTTP status codes
    api_response_extract_json = Column(JSON, nullable=True)  # JSONPath or regex patterns to extract from response
    api_follow_redirects = Column(Boolean, default=True)
    api_retry_on_status_codes = Column(ARRAY(Integer), default=[408, 429, 500, 502, 503, 504])  # retry on these codes

    # Execution Options
    timeout_seconds = Column(Integer, default=60)
    requires_elevation = Column(Boolean, default=False)  # sudo for Linux, admin for Windows
    working_directory = Column(String(255), nullable=True)
    environment_json = Column(JSON, nullable=True)  # Extra env vars

    # Error Handling
    continue_on_fail = Column(Boolean, default=False)
    retry_count = Column(Integer, default=0)
    retry_delay_seconds = Column(Integer, default=5)

    # Validation
    expected_exit_code = Column(Integer, default=0)
    expected_output_pattern = Column(String(500), nullable=True)  # Regex to match in output

    # Rollback (optional)
    rollback_command_linux = Column(Text, nullable=True)
    rollback_command_windows = Column(Text, nullable=True)

    # Relationships
    runbook = relationship("Runbook", back_populates="steps")
    api_credential_profile = relationship("APICredentialProfile")

    __table_args__ = (
        UniqueConstraint("runbook_id", "step_order", name="uq_runbook_step_order"),
        Index("idx_runbook_steps_runbook_id", "runbook_id"),
        Index("idx_runbook_steps_type", "step_type"),
    )


class RunbookTrigger(Base):
    """
    Defines when a runbook should be triggered based on alert patterns.
    Multiple triggers can point to the same runbook.
    """
    __tablename__ = "runbook_triggers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runbook_id = Column(UUID(as_uuid=True), ForeignKey("runbooks.id", ondelete="CASCADE"), nullable=False)
    
    # Matching Patterns (supports wildcards and regex)
    alert_name_pattern = Column(String(255), default="*")
    severity_pattern = Column(String(50), default="*")  # critical, warning, info, *
    instance_pattern = Column(String(255), default="*")
    job_pattern = Column(String(255), default="*")
    
    # Advanced Matching
    label_matchers_json = Column(JSON, nullable=True)  # {"env": "prod", "team": "platform"}
    annotation_matchers_json = Column(JSON, nullable=True)
    
    # Trigger Conditions
    min_duration_seconds = Column(Integer, default=0)  # Alert must be firing for X seconds
    min_occurrences = Column(Integer, default=1)  # Alert must fire X times
    
    # Priority & Status
    priority = Column(Integer, default=100, index=True)  # Lower = higher priority
    enabled = Column(Boolean, default=True, index=True)
    
    # Audit
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    # Relationships
    runbook = relationship("Runbook", back_populates="triggers")
    
    __table_args__ = (
        Index("idx_triggers_enabled_priority", "enabled", "priority"),
        Index("idx_triggers_alert_name", "alert_name_pattern"),
    )


# =============================================================================
# EXECUTION TRACKING
# =============================================================================

class RunbookExecution(Base):
    """
    Record of a runbook execution attempt.
    Tracks the full lifecycle from trigger to completion.
    """
    __tablename__ = "runbook_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # What was executed
    runbook_id = Column(UUID(as_uuid=True), ForeignKey("runbooks.id"), nullable=False)
    runbook_version = Column(Integer, nullable=False)  # Snapshot of version at execution time
    runbook_snapshot_json = Column(JSON, nullable=True)  # Full runbook config at execution time
    
    # Context
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=True)
    server_id = Column(UUID(as_uuid=True), ForeignKey("server_credentials.id"), nullable=True)
    trigger_id = Column(UUID(as_uuid=True), ForeignKey("runbook_triggers.id"), nullable=True)
    
    # Execution Mode & Status
    execution_mode = Column(String(20), default="manual")  # auto, semi_auto, manual
    status = Column(String(20), default="pending", index=True)  # pending, approved, running, success, failed, timeout, cancelled, rolled_back
    dry_run = Column(Boolean, default=False)
    
    # Approval Workflow
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # User or system
    triggered_by_system = Column(Boolean, default=False)  # True if auto-triggered
    
    approval_required = Column(Boolean, default=False)
    approval_token = Column(String(64), nullable=True, unique=True)  # For Slack/Email approval links
    approval_requested_at = Column(DateTime(timezone=True), nullable=True)
    approval_expires_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Timing
    queued_at = Column(DateTime(timezone=True), default=utc_now)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Results
    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    steps_total = Column(Integer, default=0)
    steps_completed = Column(Integer, default=0)
    steps_failed = Column(Integer, default=0)
    
    # Rollback
    rollback_executed = Column(Boolean, default=False)
    rollback_execution_id = Column(UUID(as_uuid=True), nullable=True)  # Link to rollback execution
    
    # Variables passed to execution
    variables_json = Column(JSON, nullable=True)  # Runtime parameters
    
    # Relationships
    runbook = relationship("Runbook", back_populates="executions")
    alert = relationship("Alert")
    server = relationship("ServerCredential")
    trigger = relationship("RunbookTrigger")
    triggered_by_user = relationship("User", foreign_keys=[triggered_by])
    approved_by_user = relationship("User", foreign_keys=[approved_by])
    step_executions = relationship("StepExecution", back_populates="execution", cascade="all, delete-orphan", order_by="StepExecution.step_order")
    
    __table_args__ = (
        Index("idx_executions_status", "status"),
        Index("idx_executions_runbook_status", "runbook_id", "status"),
        Index("idx_executions_alert", "alert_id"),
        Index("idx_executions_queued_at", "queued_at"),
        Index("idx_executions_approval_token", "approval_token"),
    )


class StepExecution(Base):
    """
    Record of individual step execution within a runbook execution.
    Supports both command execution and API calls.
    """
    __tablename__ = "step_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("runbook_executions.id", ondelete="CASCADE"), nullable=False)
    step_id = Column(UUID(as_uuid=True), ForeignKey("runbook_steps.id"), nullable=True)  # May be null if step was deleted

    # Step Info (snapshot)
    step_order = Column(Integer, nullable=False)
    step_name = Column(String(100), nullable=False)

    # Execution Details
    status = Column(String(20), default="pending")  # pending, running, success, failed, skipped, timeout
    command_executed = Column(Text, nullable=True)  # Actual command that was run

    # Output (for command execution)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)

    # API Response (for API execution)
    http_status_code = Column(Integer, nullable=True)  # HTTP response status code
    http_response_headers_json = Column(JSON, nullable=True)  # response headers
    http_response_body = Column(Text, nullable=True)  # raw response body
    http_request_url = Column(Text, nullable=True)  # actual URL that was called
    http_request_method = Column(String(10), nullable=True)  # HTTP method used
    extracted_values_json = Column(JSON, nullable=True)  # values extracted from response

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Retry Tracking
    retry_attempt = Column(Integer, default=0)

    # Error Info
    error_type = Column(String(50), nullable=True)  # timeout, connection, auth, command, http_error
    error_message = Column(Text, nullable=True)

    # Relationships
    execution = relationship("RunbookExecution", back_populates="step_executions")
    step = relationship("RunbookStep")

    __table_args__ = (
        Index("idx_step_executions_execution_id", "execution_id"),
        Index("idx_step_executions_status", "status"),
    )


# =============================================================================
# SAFETY MECHANISMS
# =============================================================================

class CircuitBreaker(Base):
    """
    Circuit breaker state tracking.
    Prevents cascading failures by disabling auto-execution when too many failures occur.
    """
    __tablename__ = "circuit_breakers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Scope: what this circuit breaker protects
    scope = Column(String(20), nullable=False)  # "runbook", "server", "global"
    scope_id = Column(UUID(as_uuid=True), nullable=True)  # ID of runbook or server (null for global)
    
    # State
    state = Column(String(20), default="closed")  # closed, open, half_open
    
    # Counters
    failure_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    
    # Timing
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    closes_at = Column(DateTime(timezone=True), nullable=True)  # When to transition to half-open
    
    # Configuration (can be overridden per-scope)
    failure_threshold = Column(Integer, default=3)
    failure_window_minutes = Column(Integer, default=60)
    open_duration_minutes = Column(Integer, default=30)
    
    # Manual Override
    manually_opened = Column(Boolean, default=False)
    manually_opened_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    manually_opened_reason = Column(Text, nullable=True)
    
    # Audit
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    __table_args__ = (
        UniqueConstraint("scope", "scope_id", name="uq_circuit_breaker_scope"),
        Index("idx_circuit_breaker_state", "state"),
    )


class BlackoutWindow(Base):
    """
    Time windows during which auto-remediation is disabled.
    Supports one-time and recurring schedules.
    """
    __tablename__ = "blackout_windows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic Info
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Schedule
    recurrence = Column(String(20), default="once")  # once, daily, weekly, monthly
    
    # For "once" - absolute datetime
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    
    # For recurring - time of day and days
    daily_start_time = Column(String(5), nullable=True)  # "09:00" (HH:MM)
    daily_end_time = Column(String(5), nullable=True)  # "17:00"
    days_of_week = Column(ARRAY(Integer), nullable=True)  # 0=Monday, 6=Sunday
    days_of_month = Column(ARRAY(Integer), nullable=True)  # 1-31
    
    timezone = Column(String(50), default="UTC")
    
    # Scope
    applies_to = Column(String(20), default="auto_only")  # "all", "auto_only", "specific_runbooks"
    applies_to_runbook_ids = Column(ARRAY(UUID(as_uuid=True)), default=[])
    
    # Status
    enabled = Column(Boolean, default=True, index=True)
    
    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    # Relationships
    created_by_user = relationship("User")
    
    __table_args__ = (
        Index("idx_blackout_enabled", "enabled"),
    )


class ExecutionRateLimit(Base):
    """
    Tracks execution counts for rate limiting.
    Uses sliding window counters.
    """
    __tablename__ = "execution_rate_limits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Scope
    scope = Column(String(20), nullable=False)  # "runbook", "server", "global"
    scope_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Window
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    
    # Counter
    execution_count = Column(Integer, default=0)
    last_execution_at = Column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        UniqueConstraint("scope", "scope_id", "window_start", name="uq_rate_limit_window"),
        Index("idx_rate_limit_scope_window", "scope", "scope_id", "window_start"),
    )


# =============================================================================
# COMMAND SAFETY
# =============================================================================

class CommandBlocklist(Base):
    """
    Dangerous commands that should never be executed.
    """
    __tablename__ = "command_blocklist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    pattern = Column(String(500), nullable=False, unique=True)  # Regex pattern
    pattern_type = Column(String(20), default="regex")  # "regex", "contains", "exact"
    os_type = Column(String(10), default="any")  # "linux", "windows", "any"
    
    description = Column(Text, nullable=True)  # Why this is blocked
    severity = Column(String(20), default="critical")  # "critical", "warning"
    
    enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now)
    
    __table_args__ = (
        Index("idx_blocklist_enabled_os", "enabled", "os_type"),
    )


class CommandAllowlist(Base):
    """
    Optional allowlist - if enabled, only these commands can be executed.
    """
    __tablename__ = "command_allowlist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    pattern = Column(String(500), nullable=False, unique=True)  # Regex pattern
    pattern_type = Column(String(20), default="regex")
    os_type = Column(String(10), default="any")
    
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)  # "service-management", "file-cleanup", etc.
    
    enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now)
    
    __table_args__ = (
        Index("idx_allowlist_enabled_os", "enabled", "os_type"),
    )
