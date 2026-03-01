"""
Password Policy Service

Manages the organisational password policy stored in system_config
and provides validation logic enforced at user creation / password update.

Policy keys (stored as system_config key='password_policy', value_json=<dict>):
  min_length            int   Minimum password length (default 8)
  max_length            int   Maximum password length (default 128, 0 = no limit)
  require_uppercase     bool  At least one A-Z character
  require_lowercase     bool  At least one a-z character
  require_numbers       bool  At least one 0-9 digit
  require_special_chars bool  At least one special character (!@#$%^&*…)
  password_expiry_days  int   Days before password expires (0 = never)
  max_login_attempts    int   Failed attempts before account lockout (0 = disabled)
  lockout_duration_mins int   Minutes account stays locked (default 30)
"""
import re
from typing import Optional
from sqlalchemy.orm import Session

from app.models import SystemConfig

# ──────────────────────────────────────────────────────────────────────────────
#  Defaults — industry-standard baseline
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_PASSWORD_POLICY: dict = {
    "min_length": 8,
    "max_length": 128,
    "require_uppercase": False,
    "require_lowercase": False,
    "require_numbers": False,
    "require_special_chars": False,
    "password_expiry_days": 0,       # 0 = never expires
    "max_login_attempts": 0,         # 0 = no lockout
    "lockout_duration_mins": 30,
}

_CONFIG_KEY = "password_policy"


# ──────────────────────────────────────────────────────────────────────────────
#  CRUD helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_password_policy(db: Session) -> dict:
    """
    Return the current password policy from system_config.
    Falls back to DEFAULT_PASSWORD_POLICY when no record exists.
    """
    row = db.query(SystemConfig).filter(SystemConfig.key == _CONFIG_KEY).first()
    if row and isinstance(row.value_json, dict):
        # Merge with defaults so any new keys added in future always have a value
        policy = {**DEFAULT_PASSWORD_POLICY, **row.value_json}
    else:
        policy = DEFAULT_PASSWORD_POLICY.copy()
    return policy


def save_password_policy(db: Session, policy: dict, user_id=None) -> dict:
    """
    Persist the password policy to system_config.
    Merges with defaults to ensure all keys are present.
    Returns the saved (merged) policy.
    """
    merged = {**DEFAULT_PASSWORD_POLICY, **policy}

    # Clamp / coerce values
    merged["min_length"] = max(1, int(merged.get("min_length", 8)))
    max_len = int(merged.get("max_length", 128))
    merged["max_length"] = max_len if max_len > 0 else 0
    if max_len > 0:
        merged["max_length"] = max(merged["min_length"], max_len)
    merged["password_expiry_days"] = max(0, int(merged.get("password_expiry_days", 0)))
    merged["max_login_attempts"] = max(0, int(merged.get("max_login_attempts", 0)))
    merged["lockout_duration_mins"] = max(1, int(merged.get("lockout_duration_mins", 30)))

    row = db.query(SystemConfig).filter(SystemConfig.key == _CONFIG_KEY).first()
    if row:
        row.value_json = merged
        row.updated_by = user_id
    else:
        row = SystemConfig(key=_CONFIG_KEY, value_json=merged, updated_by=user_id)
        db.add(row)

    db.commit()
    db.refresh(row)
    return row.value_json


# ──────────────────────────────────────────────────────────────────────────────
#  Validation
# ──────────────────────────────────────────────────────────────────────────────

SPECIAL_CHARS = r"!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~"


def validate_password(password: str, policy: Optional[dict] = None) -> list[str]:
    """
    Validate *password* against *policy*.
    Returns a list of violation messages (empty == valid).

    ``policy`` defaults to DEFAULT_PASSWORD_POLICY when None.
    """
    if policy is None:
        policy = DEFAULT_PASSWORD_POLICY

    errors: list[str] = []
    p = password or ""

    min_len = int(policy.get("min_length", 8))
    max_len = int(policy.get("max_length", 128))

    if len(p) < min_len:
        errors.append(f"Password must be at least {min_len} characters long.")

    if max_len > 0 and len(p) > max_len:
        errors.append(f"Password must not exceed {max_len} characters.")

    if policy.get("require_uppercase") and not re.search(r"[A-Z]", p):
        errors.append("Password must contain at least one uppercase letter (A-Z).")

    if policy.get("require_lowercase") and not re.search(r"[a-z]", p):
        errors.append("Password must contain at least one lowercase letter (a-z).")

    if policy.get("require_numbers") and not re.search(r"[0-9]", p):
        errors.append("Password must contain at least one digit (0-9).")

    if policy.get("require_special_chars") and not re.search(
        rf"[{SPECIAL_CHARS}]", p
    ):
        errors.append(
            "Password must contain at least one special character "
            "(!@#$%^&*()_+-=[]{};\\':\"|,.<>/?`~)."
        )

    return errors


def enforce_password_policy(password: str, db: Session) -> None:
    """
    Validate password against the stored policy.
    Raises ``ValueError`` with a human-readable message on failure.
    Does NOT raise when there are no violations.
    """
    policy = get_password_policy(db)
    errors = validate_password(password, policy)
    if errors:
        raise ValueError(" ".join(errors))
