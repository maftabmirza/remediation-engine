"""
Alert Suppression Rules API (Feature A6)

CRUD endpoints for managing alert suppression rules.
Suppressed alerts are still persisted but are skipped for analysis and
auto-remediation (marked with action_taken="suppressed").
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog, User
from app.schemas import (
    SuppressionCheckResult,
    SuppressionRuleCreate,
    SuppressionRuleListResponse,
    SuppressionRuleResponse,
    SuppressionRuleUpdate,
)
from app.services.alert_suppression_service import AlertSuppressionService
from app.services.auth_service import get_current_user, require_admin

router = APIRouter(prefix="/api/suppression-rules", tags=["Suppression Rules"])


@router.get("", response_model=SuppressionRuleListResponse)
async def list_suppression_rules(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    active_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuppressionRuleListResponse:
    """
    List all alert suppression rules (paginated).

    Query parameters:
    - **page**: Page number (1-based).
    - **page_size**: Results per page (max 100).
    - **active_only**: When true, return only rules that are currently active.
    """
    svc = AlertSuppressionService(db)
    rules, total = svc.list_rules(page=page, page_size=page_size, active_only=active_only)
    return SuppressionRuleListResponse(
        rules=[SuppressionRuleResponse.model_validate(r) for r in rules],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=SuppressionRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_suppression_rule(
    request: Request,
    body: SuppressionRuleCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SuppressionRuleResponse:
    """
    Create a new alert suppression rule.  **Admin only.**

    A suppression rule silences incoming alerts matching all four patterns
    (`alert_name_pattern`, `severity_pattern`, `instance_pattern`,
    `job_pattern`).  Patterns follow the same wildcard syntax as
    auto-analyze rules (``*`` matches everything, ``?`` matches one char).

    An optional time window (``starts_at`` / ``ends_at``) restricts the rule
    to a maintenance period.
    """
    svc = AlertSuppressionService(db)
    try:
        rule = svc.create_rule(
            name=body.name,
            description=body.description,
            alert_name_pattern=body.alert_name_pattern,
            severity_pattern=body.severity_pattern,
            instance_pattern=body.instance_pattern,
            job_pattern=body.job_pattern,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            is_active=body.is_active,
            reason=body.reason,
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    _audit(db, current_user.id, "create_suppression_rule", rule.id, {"name": rule.name}, request)
    return SuppressionRuleResponse.model_validate(rule)


@router.get("/{rule_id}", response_model=SuppressionRuleResponse)
async def get_suppression_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuppressionRuleResponse:
    """Get a specific suppression rule by ID."""
    svc = AlertSuppressionService(db)
    rule = svc.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suppression rule not found")
    return SuppressionRuleResponse.model_validate(rule)


@router.put("/{rule_id}", response_model=SuppressionRuleResponse)
async def update_suppression_rule(
    rule_id: UUID,
    request: Request,
    body: SuppressionRuleUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SuppressionRuleResponse:
    """
    Update an existing suppression rule.  **Admin only.**

    Only the fields included in the request body are updated.
    """
    svc = AlertSuppressionService(db)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update")

    try:
        rule = svc.update_rule(rule_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suppression rule not found")

    _audit(db, current_user.id, "update_suppression_rule", rule.id, {"updated_fields": list(updates.keys())}, request)
    return SuppressionRuleResponse.model_validate(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_suppression_rule(
    rule_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    """Delete a suppression rule.  **Admin only.**"""
    svc = AlertSuppressionService(db)
    deleted = svc.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suppression rule not found")

    _audit(db, current_user.id, "delete_suppression_rule", rule_id, {}, request)


@router.post("/check", response_model=SuppressionCheckResult)
async def check_alert_suppression(
    alert_name: str = Query(...),
    severity: str = Query(default=""),
    instance: str = Query(default=""),
    job: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuppressionCheckResult:
    """
    Check whether an alert with the given labels would be suppressed.

    Useful for testing suppression rules before deploying them.
    """
    svc = AlertSuppressionService(db)
    suppressed, rule = svc.check_suppressed(alert_name, severity, instance, job)
    return SuppressionCheckResult(
        suppressed=suppressed,
        rule_id=rule.id if rule else None,
        rule_name=rule.name if rule else None,
        reason=rule.reason if rule else None,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _audit(
    db: Session,
    user_id: UUID,
    action: str,
    resource_id: UUID,
    details: dict,
    request: Request,
) -> None:
    """Append an entry to the audit log (best-effort, non-blocking)."""
    try:
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type="suppression_rule",
            resource_id=resource_id,
            details_json=details,
            ip_address=request.client.host if request.client else None,
        )
        db.add(log)
        db.commit()
    except Exception:
        pass
