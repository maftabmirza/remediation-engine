"""SQLAlchemy ORM Models"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, DateTime, JSON, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from typing import TYPE_CHECKING
from pgvector.sqlalchemy import Vector

from app.database import Base
if TYPE_CHECKING:
    pass
else:
    # Avoid runtime circular import but allow SQLAlchemy to find models if needed
    from app.models_learning import AnalysisFeedback
    from app.models_troubleshooting import AlertCorrelation
    from app.models_agent import AgentSession, AgentStep
    from app.models_iteration import IterationLoop
    from app.models_agent_pool import AgentPool, AgentTask, ActionProposal


def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    full_name = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="operator")
    default_llm_provider_id = Column(UUID(as_uuid=True), ForeignKey("llm_providers.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    last_login = Column(DateTime(timezone=True), nullable=True)
    ai_preferences = Column(JSON, default={}, nullable=True)

    # Relationships
    default_llm_provider = relationship("LLMProvider", foreign_keys=[default_llm_provider_id])
    rules_created = relationship("AutoAnalyzeRule", back_populates="created_by_user")
    alerts_analyzed = relationship("Alert", back_populates="analyzed_by_user")


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    permissions = Column(JSON, default=[], nullable=False)
    is_custom = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class LLMProvider(Base):
    __tablename__ = "llm_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    provider_type = Column(String(50), nullable=False, index=True)  # anthropic, openai, google, ollama
    model_id = Column(String(100), nullable=False)
    api_key_encrypted = Column(Text, nullable=True)
    api_base_url = Column(String(255), nullable=True)
    is_default = Column(Boolean, default=False, index=True)
    is_enabled = Column(Boolean, default=True, index=True)
    config_json = Column(JSON, default={"temperature": 0.3, "max_tokens": 2000})
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AutoAnalyzeRule(Base):
    __tablename__ = "auto_analyze_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=100, index=True)  # Lower = higher priority
    condition_json = Column(JSON, nullable=True)
    alert_name_pattern = Column(String(255), default="*")
    severity_pattern = Column(String(50), default="*")
    instance_pattern = Column(String(255), default="*")
    job_pattern = Column(String(255), default="*")
    action = Column(String(20), default="manual")  # auto_analyze, ignore, manual
    enabled = Column(Boolean, default=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    created_by_user = relationship("User", back_populates="rules_created")
    matched_alerts = relationship("Alert", back_populates="matched_rule")


class AlertCluster(Base):
    """Alert cluster for grouping related alerts"""
    __tablename__ = "alert_clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_key = Column(String(255), unique=True, nullable=False, index=True)
    alert_count = Column(Integer, default=1, nullable=False)
    first_seen = Column(DateTime(timezone=True), nullable=False, index=True)
    last_seen = Column(DateTime(timezone=True), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    cluster_type = Column(String(50), default='exact', nullable=False)
    summary = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    closed_reason = Column(String(100), nullable=True)
    cluster_metadata = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    alerts = relationship("Alert", back_populates="cluster")

    @property
    def duration_hours(self):
        """Calculate cluster duration in hours"""
        if not self.first_seen or not self.last_seen:
            return 0.0
        delta = self.last_seen - self.first_seen
        return delta.total_seconds() / 3600

    @property
    def alerts_per_hour(self):
        """Calculate alert frequency"""
        if self.duration_hours == 0:
            return float(self.alert_count)
        return self.alert_count / self.duration_hours

    def update_stats(self, db):
        """Recalculate cluster statistics"""
        from sqlalchemy.orm import Session
        alerts = db.query(Alert).filter(Alert.cluster_id == self.id).all()

        if not alerts:
            return

        self.alert_count = len(alerts)
        self.first_seen = min(a.timestamp for a in alerts)
        self.last_seen = max(a.timestamp for a in alerts)

        # Update severity to highest
        severity_order = {'critical': 3, 'warning': 2, 'info': 1}
        severities = [a.severity for a in alerts if a.severity]
        if severities:
            self.severity = max(severities, key=lambda s: severity_order.get(s, 0))

        self.updated_at = utc_now()

    def should_close(self, inactive_hours=24):
        """Check if cluster should be closed due to inactivity"""
        if not self.is_active:
            return False

        inactive_duration = utc_now() - self.last_seen
        return inactive_duration.total_seconds() / 3600 >= inactive_hours


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fingerprint = Column(String(100), index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    alert_name = Column(String(255), nullable=False, index=True)
    severity = Column(String(50), index=True)
    instance = Column(String(255))
    job = Column(String(100))
    status = Column(String(20), default="firing", index=True)  # firing, resolved
    labels_json = Column(JSON)
    annotations_json = Column(JSON)
    raw_alert_json = Column(JSON)
    matched_rule_id = Column(UUID(as_uuid=True), ForeignKey("auto_analyze_rules.id"), nullable=True)
    action_taken = Column(String(20), index=True)  # auto_analyze, ignore, manual, pending
    analyzed = Column(Boolean, default=False, index=True)
    analyzed_at = Column(DateTime(timezone=True), nullable=True)
    analyzed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    llm_provider_id = Column(UUID(as_uuid=True), ForeignKey("llm_providers.id"), nullable=True)
    ai_analysis = Column(Text, nullable=True)
    recommendations_json = Column(JSON, nullable=True)
    analysis_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    
    # Application/Component linking
    app_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True)
    component_id = Column(UUID(as_uuid=True), ForeignKey("application_components.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Vector embeddings for similarity search
    embedding = Column(Vector(1536), nullable=True)
    embedding_text = Column(Text, nullable=True)
    
    # Correlation/Troubleshooting
    correlation_id = Column(UUID(as_uuid=True), ForeignKey("alert_correlations.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Alert Clustering
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("alert_clusters.id", ondelete="SET NULL"), nullable=True, index=True)
    clustered_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    matched_rule = relationship("AutoAnalyzeRule", back_populates="matched_alerts")
    analyzed_by_user = relationship("User", back_populates="alerts_analyzed")
    llm_provider = relationship("LLMProvider")
    application = relationship("Application", back_populates="alerts")
    component = relationship("ApplicationComponent", back_populates="alerts")
    feedback = relationship("AnalysisFeedback", back_populates="alert", cascade="all, delete-orphan")
    correlation = relationship("AlertCorrelation", back_populates="alerts")
    cluster = relationship("AlertCluster", back_populates="alerts")
    metrics = relationship("IncidentMetrics", back_populates="alert", uselist=False)



class IncidentMetrics(Base):
    """Detailed incident timeline metrics"""
    __tablename__ = "incident_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Lifecycle timestamps
    incident_started = Column(DateTime(timezone=True), nullable=False)
    incident_detected = Column(DateTime(timezone=True), nullable=False)
    incident_acknowledged = Column(DateTime(timezone=True))
    incident_engaged = Column(DateTime(timezone=True))
    incident_resolved = Column(DateTime(timezone=True))

    # Calculated durations (seconds)
    time_to_detect = Column(Integer)
    time_to_acknowledge = Column(Integer)
    time_to_engage = Column(Integer)
    time_to_resolve = Column(Integer)

    # Context
    service_name = Column(String(255), index=True)
    severity = Column(String(20), index=True)
    resolution_type = Column(String(50), index=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    alert = relationship("Alert", back_populates="metrics")
    assignee = relationship("User")

    def calculate_durations(self):
        """Calculate all time_to_* fields from timestamps"""
        if self.incident_detected and self.incident_started:
            self.time_to_detect = int((self.incident_detected - self.incident_started).total_seconds())

        if self.incident_acknowledged and self.incident_detected:
            self.time_to_acknowledge = int((self.incident_acknowledged - self.incident_detected).total_seconds())

        if self.incident_engaged and self.incident_acknowledged:
            self.time_to_engage = int((self.incident_engaged - self.incident_acknowledged).total_seconds())

        if self.incident_resolved and self.incident_engaged:
            self.time_to_resolve = int((self.incident_resolved - self.incident_engaged).total_seconds())


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True, index=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    details_json = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    # Relationships
    user = relationship("User")


class ServerCredential(Base):
    """
    Server connection credentials.
    Supports Linux (SSH), Windows (WinRM), and API endpoints (HTTP/REST).
    """
    __tablename__ = "server_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    hostname = Column(String(255), nullable=False, index=True)
    port = Column(Integer, default=22)
    username = Column(String(100), nullable=False)

    # Platform Configuration
    os_type = Column(String(20), default="linux", index=True)  # "linux", "windows"
    protocol = Column(String(20), default="ssh", index=True)  # "ssh", "winrm", "api"

    # SSH Authentication (Linux, or Windows via SSH)
    auth_type = Column(String(20), default="key")  # key, password
    ssh_key_encrypted = Column(Text, nullable=True)
    password_encrypted = Column(Text, nullable=True)

    # External credential stores
    credential_source = Column(String(30), default="inline", index=True)  # inline, shared_profile
    credential_profile_id = Column(UUID(as_uuid=True), ForeignKey("credential_profiles.id"), nullable=True, index=True)
    credential_metadata = Column(JSON, default={})

    # WinRM Configuration (Windows)
    winrm_transport = Column(String(20), nullable=True)  # "kerberos", "ntlm", "certificate"
    winrm_use_ssl = Column(Boolean, default=True)
    winrm_cert_validation = Column(Boolean, default=True)
    domain = Column(String(100), nullable=True)  # AD domain for Windows auth

    # API Configuration (HTTP/REST)
    api_base_url = Column(String(500), nullable=True)  # Base URL for API endpoints
    api_auth_type = Column(String(30), default="none")  # none, api_key, bearer, basic, oauth, custom
    api_auth_header = Column(String(100), nullable=True)  # e.g., "X-API-Key", "Authorization"
    api_token_encrypted = Column(Text, nullable=True)  # encrypted API token/key
    api_verify_ssl = Column(Boolean, default=True)
    api_timeout_seconds = Column(Integer, default=30)
    api_headers_json = Column(JSON, default={})  # default headers for all requests
    api_metadata_json = Column(JSON, default={})  # provider-specific config (e.g., AWX job template ID)

    # Environment & Tags
    environment = Column(String(50), default="production", index=True)  # production, staging, dev
    tags = Column(JSON, default=[])  # For filtering servers
    group_id = Column(UUID(as_uuid=True), ForeignKey("server_groups.id"), nullable=True, index=True)

    # Connection Testing
    last_connection_test = Column(DateTime(timezone=True), nullable=True)
    last_connection_status = Column(String(20), nullable=True)  # "success", "failed"
    last_connection_error = Column(Text, nullable=True)

    # Audit
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # Relationships
    created_by_user = relationship("User")
    group = relationship("ServerGroup", back_populates="servers")
    credential_profile = relationship("CredentialProfile", back_populates="servers")


class ServerGroup(Base):
    __tablename__ = "server_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("server_groups.id"), nullable=True, index=True)
    path = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    parent = relationship("ServerGroup", remote_side=[id])
    servers = relationship("ServerCredential", back_populates="group")


class CredentialProfile(Base):
    """Reusable credential profiles (inline secret or external vault provider)."""

    __tablename__ = "credential_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    username = Column(String(100), nullable=True, index=True)
    credential_type = Column(String(30), default="key", index=True)  # key, password, vault, cyberark
    backend = Column(String(30), default="inline", index=True)  # inline, vault, cyberark
    secret_encrypted = Column(Text, nullable=True)
    metadata_json = Column(JSON, default={})
    last_rotated = Column(DateTime(timezone=True), nullable=True)
    group_id = Column(UUID(as_uuid=True), ForeignKey("server_groups.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    group = relationship("ServerGroup")
    servers = relationship("ServerCredential", back_populates="credential_profile")


class APICredentialProfile(Base):
    """
    External API service credentials (e.g., Ansible AWX, Jenkins, Kubernetes API).
    Separate from server inventory - these are external services, not managed hosts.
    """
    __tablename__ = "api_credential_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    # Credential type
    credential_type = Column(String(50), default="api", index=True)  # api, oauth, custom

    # API Configuration
    base_url = Column(String(500), nullable=False)
    auth_type = Column(String(30), default="none", index=True)  # none, api_key, bearer, basic, oauth, custom
    auth_header = Column(String(100), nullable=True)  # e.g., 'Authorization', 'X-API-Key'
    token_encrypted = Column(Text, nullable=True)  # Encrypted API token/password
    username = Column(String(255), nullable=True)  # For basic auth or OAuth

    # HTTP Configuration
    verify_ssl = Column(Boolean, default=True)
    timeout_seconds = Column(Integer, default=30)
    default_headers = Column(JSON, default={})

    # OAuth specific (for future expansion)
    oauth_token_url = Column(String(500), nullable=True)
    oauth_client_id = Column(String(255), nullable=True)
    oauth_client_secret_encrypted = Column(Text, nullable=True)
    oauth_scope = Column(Text, nullable=True)

    # Metadata and tags
    tags = Column(JSON, default=[])
    profile_metadata = Column(JSON, default={})

    # Status
    enabled = Column(Boolean, default=True, index=True)

    # Audit fields
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    created_by_user = relationship("User")


class TerminalSession(Base):
    __tablename__ = "terminal_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    server_credential_id = Column(UUID(as_uuid=True), ForeignKey("server_credentials.id"), nullable=False)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=True)
    started_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    recording_path = Column(String(255), nullable=True)

    # Relationships
    user = relationship("User")
    server = relationship("ServerCredential")
    alert = relationship("Alert")


class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String(50), primary_key=True)
    value_json = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class SolutionOutcome(Base):
    """Track what solutions worked for which problems - enables learning from feedback."""
    __tablename__ = "solution_outcomes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Session context
    session_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Problem context (for similarity matching)
    problem_description = Column(Text, nullable=False)
    problem_embedding = Column(Vector(1536), nullable=True)  # For similarity search
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, index=True)
    server_id = Column(UUID(as_uuid=True), ForeignKey("server_credentials.id", ondelete="SET NULL"), nullable=True, index=True)

    # What was suggested
    solution_type = Column(String(50), nullable=False)  # 'runbook', 'command', 'knowledge', 'agent_suggestion'
    solution_reference = Column(Text, nullable=True)     # runbook_id, command text, knowledge doc id
    solution_summary = Column(Text, nullable=True)       # Brief description

    # Outcome (from user feedback or auto-detection)
    success = Column(Boolean, nullable=True)
    auto_detected = Column(Boolean, default=False)  # Was success auto-detected from terminal?
    user_feedback = Column(Text, nullable=True)
    feedback_timestamp = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)

    # Relationships
    alert = relationship("Alert")
    server = relationship("ServerCredential")
