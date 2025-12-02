"""
Services package
"""
from app.services.auth_service import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
    get_user_by_username,
    get_user_by_id,
    authenticate_user,
    create_user,
    get_current_user,
    get_current_user_optional,
    require_admin,
    require_role
)

from app.services.rules_engine import (
    match_pattern,
    match_rule,
    find_matching_rule,
    evaluate_alert,
    test_rules
)

from app.services.llm_service import (
    analyze_alert,
    get_available_providers,
    get_default_provider
)

# Auto-Remediation Services
from app.services.executor_base import (
    ExecutionResult,
    BaseExecutor,
    ErrorType,
    ServerInfo
)

from app.services.executor_ssh import SSHExecutor

from app.services.executor_factory import ExecutorFactory

from app.services.runbook_executor import RunbookExecutor

from app.services.command_validator import (
    CommandValidator,
    CommandValidation,
    ValidationResult,
    validate_command
)

from app.services.trigger_matcher import (
    AlertTriggerMatcher,
    ApprovalService,
    TriggerMatch,
    MatchResult
)

from app.services.safety_mechanisms import (
    CircuitBreakerService,
    RateLimitService,
    BlackoutWindowService,
    SafetyGate,
    SafetyCheckResult
)
