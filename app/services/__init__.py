"""Services package.

Keep imports lightweight.

Historically this package re-exported many symbols (e.g. `from app.services import create_access_token`).
Importing them eagerly makes *any* import under `app.services.*` pull in optional/large dependencies
(e.g. `python-jose`, DB drivers, LLM SDKs), which breaks unit-test environments and slows startup.

We preserve the public re-exports via lazy imports (PEP 562).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import importlib


_EXPORTS: dict[str, tuple[str, str]] = {
    # auth_service
    "verify_password": ("app.services.auth_service", "verify_password"),
    "get_password_hash": ("app.services.auth_service", "get_password_hash"),
    "create_access_token": ("app.services.auth_service", "create_access_token"),
    "decode_token": ("app.services.auth_service", "decode_token"),
    "get_user_by_username": ("app.services.auth_service", "get_user_by_username"),
    "get_user_by_id": ("app.services.auth_service", "get_user_by_id"),
    "authenticate_user": ("app.services.auth_service", "authenticate_user"),
    "create_user": ("app.services.auth_service", "create_user"),
    "get_current_user": ("app.services.auth_service", "get_current_user"),
    "get_current_user_optional": ("app.services.auth_service", "get_current_user_optional"),
    "require_admin": ("app.services.auth_service", "require_admin"),
    "require_role": ("app.services.auth_service", "require_role"),

    # rules_engine
    "match_pattern": ("app.services.rules_engine", "match_pattern"),
    "match_rule": ("app.services.rules_engine", "match_rule"),
    "find_matching_rule": ("app.services.rules_engine", "find_matching_rule"),
    "evaluate_alert": ("app.services.rules_engine", "evaluate_alert"),
    "test_rules": ("app.services.rules_engine", "test_rules"),

    # llm_service
    "analyze_alert": ("app.services.llm_service", "analyze_alert"),
    "get_available_providers": ("app.services.llm_service", "get_available_providers"),
    "get_default_provider": ("app.services.llm_service", "get_default_provider"),

    # executor_base
    "ExecutionResult": ("app.services.executor_base", "ExecutionResult"),
    "BaseExecutor": ("app.services.executor_base", "BaseExecutor"),
    "ErrorType": ("app.services.executor_base", "ErrorType"),
    "ServerInfo": ("app.services.executor_base", "ServerInfo"),

    # executors / factories
    "SSHExecutor": ("app.services.executor_ssh", "SSHExecutor"),
    "ExecutorFactory": ("app.services.executor_factory", "ExecutorFactory"),
    "RunbookExecutor": ("app.services.runbook_executor", "RunbookExecutor"),

    # command_validator
    "CommandValidator": ("app.services.command_validator", "CommandValidator"),
    "CommandValidation": ("app.services.command_validator", "CommandValidation"),
    "ValidationResult": ("app.services.command_validator", "ValidationResult"),
    "validate_command": ("app.services.command_validator", "validate_command"),

    # trigger_matcher
    "AlertTriggerMatcher": ("app.services.trigger_matcher", "AlertTriggerMatcher"),
    "ApprovalService": ("app.services.trigger_matcher", "ApprovalService"),
    "TriggerMatch": ("app.services.trigger_matcher", "TriggerMatch"),
    "MatchResult": ("app.services.trigger_matcher", "MatchResult"),

    # safety_mechanisms
    "CircuitBreakerService": ("app.services.safety_mechanisms", "CircuitBreakerService"),
    "RateLimitService": ("app.services.safety_mechanisms", "RateLimitService"),
    "BlackoutWindowService": ("app.services.safety_mechanisms", "BlackoutWindowService"),
    "SafetyGate": ("app.services.safety_mechanisms", "SafetyGate"),
    "SafetyCheckResult": ("app.services.safety_mechanisms", "SafetyCheckResult"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = target
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(list(globals().keys()) + list(_EXPORTS.keys())))


__all__ = sorted(_EXPORTS.keys())


if TYPE_CHECKING:
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
        require_role,
    )
    from app.services.rules_engine import (
        match_pattern,
        match_rule,
        find_matching_rule,
        evaluate_alert,
        test_rules,
    )
    from app.services.llm_service import (
        analyze_alert,
        get_available_providers,
        get_default_provider,
    )
    from app.services.executor_base import ExecutionResult, BaseExecutor, ErrorType, ServerInfo
    from app.services.executor_ssh import SSHExecutor
    from app.services.executor_factory import ExecutorFactory
    from app.services.runbook_executor import RunbookExecutor
    from app.services.command_validator import (
        CommandValidator,
        CommandValidation,
        ValidationResult,
        validate_command,
    )
    from app.services.trigger_matcher import AlertTriggerMatcher, ApprovalService, TriggerMatch, MatchResult
    from app.services.safety_mechanisms import (
        CircuitBreakerService,
        RateLimitService,
        BlackoutWindowService,
        SafetyGate,
        SafetyCheckResult,
    )
