"""
Rules Engine - Match alerts against auto-analyze rules
"""
import fnmatch
import re
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session

try:
    from json_logic import jsonLogic
except ImportError:
    jsonLogic = None

from app.models import AutoAnalyzeRule, Alert


def match_pattern(pattern: str, value: str) -> bool:
    """
    Match a value against a pattern.
    Supports:
    - '*' matches everything
    - Simple wildcards: 'prod-*', '*.example.com'
    - Exact match: 'HighCPU'
    """
    if pattern == "*":
        return True
    
    if not value:
        return pattern == "*"
    
    # Convert wildcard pattern to regex
    # Escape special regex chars except * and ?
    regex_pattern = re.escape(pattern)
    regex_pattern = regex_pattern.replace(r'\*', '.*')
    regex_pattern = regex_pattern.replace(r'\?', '.')
    regex_pattern = f'^{regex_pattern}$'
    
    try:
        return bool(re.match(regex_pattern, value, re.IGNORECASE))
    except re.error:
        # Fallback to fnmatch if regex fails
        return fnmatch.fnmatch(value.lower(), pattern.lower())


def flatten_alert(alert_name: str, severity: str, instance: str, job: str) -> Dict[str, Any]:
    """Helper to create a data dict for JSON logic."""
    return {
        "alert_name": alert_name,
        "severity": severity,
        "instance": instance,
        "job": job,
        # Flattened for easier access if we had more fields, 
        # but for now this matches the logic arguments
    }


def match_rule(rule: AutoAnalyzeRule, alert_name: str, severity: str, instance: str, job: str) -> bool:
    """
    Check if an alert matches a rule's patterns.
    Prioritizes JSON logic if present.
    """
    if not rule.enabled:
        return False
        
    # 1. Advanced JSON Logic
    if rule.condition_json:
        if not jsonLogic:
            # Log warning?
            return False 
            
        data = {
            "alert_name": alert_name,
            "severity": severity,
            "instance": instance,
            "job": job
        }
        try:
            return bool(jsonLogic(rule.condition_json, data))
        except Exception:
            return False

    # 2. Legacy Pattern Matching
    # All patterns must match
    if not match_pattern(rule.alert_name_pattern, alert_name or ""):
        return False
    if not match_pattern(rule.severity_pattern, severity or ""):
        return False
    if not match_pattern(rule.instance_pattern, instance or ""):
        return False
    if not match_pattern(rule.job_pattern, job or ""):
        return False
    
    return True


def find_matching_rule(
    db: Session,
    alert_name: str,
    severity: str,
    instance: str,
    job: str
) -> Tuple[Optional[AutoAnalyzeRule], str]:
    """
    Find the first matching rule for an alert.
    Rules are evaluated in priority order (lower number = higher priority).
    
    Returns:
        Tuple of (matched_rule, action)
        If no rule matches, returns (None, 'manual')
    """
    # Get all enabled rules ordered by priority
    rules = db.query(AutoAnalyzeRule).filter(
        AutoAnalyzeRule.enabled == True
    ).order_by(AutoAnalyzeRule.priority.asc()).all()
    
    for rule in rules:
        if match_rule(rule, alert_name, severity, instance, job):
            return (rule, rule.action)
    
    # Default to manual if no rule matches
    return (None, "manual")


def evaluate_alert(db: Session, alert: Alert) -> Tuple[Optional[AutoAnalyzeRule], str]:
    """
    Evaluate an alert against all rules and return the matching rule and action.
    """
    return find_matching_rule(
        db,
        alert.alert_name,
        alert.severity,
        alert.instance,
        alert.job
    )


def test_rules(
    db: Session,
    alert_name: str,
    severity: str,
    instance: str,
    job: str
) -> dict:
    """
    Test which rule would match for given alert parameters.
    """
    matched_rule, action = find_matching_rule(db, alert_name, severity, instance, job)
    
    return {
        "matched_rule": matched_rule,
        "action": action,
        "message": f"Alert would be processed with action: {action}" + 
                   (f" (Rule: {matched_rule.name})" if matched_rule else " (No rule matched, using default)")
    }
