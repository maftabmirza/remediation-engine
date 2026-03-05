"""
Alert Suppression Rules API

CRUD endpoints for managing alert suppression rules plus a dry-run
check endpoint to test whether a given set of labels would be suppressed.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models_suppression import AlertSuppressionRule
from app.schemas_suppression import (
    AlertSuppressionRuleCreate,
    AlertSuppressionRuleListResponse,
    AlertSuppressionRuleResponse,
    AlertSuppressionRuleUpdate,
    SuppressionCheckRequest,
    SuppressionCheckResponse,
)
from app.services.alert_suppression_service import AlertSuppressionService
from app.services.auth_service import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alert-suppression", tags=["alert-suppression"])


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=AlertSuppressionRuleListResponse,
    summary="List all alert suppression rules (paginated)",
)
def list_suppression_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    active_only: bool = Query(False, description="Return only active rules"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertSuppressionRuleListResponse:
    """
    List suppression rules with optional active-only filter.

    Args:
        page: Page number (1-indexed).
        page_size: Number of results per page (max 100).
        active_only: When True, only return rules where is_active=True.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Paginated list of suppression rules.
    """
    query = db.query(AlertSuppressionRule)
    if active_only:
        query = query.filter(AlertSuppressionRule.is_active.is_(True))

    total = query.count()
    rules = (
        query.order_by(AlertSuppressionRule.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return AlertSuppressionRuleListResponse(
        rules=[AlertSuppressionRuleResponse.model_validate(r) for r in rules],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=AlertSuppressionRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new suppression rule",
)
def create_suppression_rule(
    payload: AlertSuppressionRuleCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AlertSuppressionRuleResponse:
    """
    Create a new alert suppression rule.

    Args:
        payload: Rule definition.
        current_user: Admin-level authenticated user.
        db: Database session.

    Returns:
        The newly created suppression rule.
    """
    rule = AlertSuppressionRule(
        **payload.model_dump(),
        created_by=current_user.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    logger.info(
        "Suppression rule '%s' created by %s", rule.name, current_user.username
    )
    return AlertSuppressionRuleResponse.model_validate(rule)


# ---------------------------------------------------------------------------
# Get single
# ---------------------------------------------------------------------------


@router.get(
    "/{rule_id}",
    response_model=AlertSuppressionRuleResponse,
    summary="Get a single suppression rule by ID",
)
def get_suppression_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertSuppressionRuleResponse:
    """
    Retrieve a suppression rule by its UUID.

    Args:
        rule_id: UUID of the suppression rule.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        The suppression rule.

    Raises:
        HTTPException: 404 if the rule does not exist.
    """
    rule = (
        db.query(AlertSuppressionRule)
        .filter(AlertSuppressionRule.id == rule_id)
        .first()
    )
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suppression rule {rule_id} not found",
        )
    return AlertSuppressionRuleResponse.model_validate(rule)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.put(
    "/{rule_id}",
    response_model=AlertSuppressionRuleResponse,
    summary="Update an existing suppression rule",
)
def update_suppression_rule(
    rule_id: UUID,
    payload: AlertSuppressionRuleUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AlertSuppressionRuleResponse:
    """
    Update an existing suppression rule (partial update).

    Args:
        rule_id: UUID of the suppression rule.
        payload: Fields to update (only non-None fields are applied).
        current_user: Admin-level authenticated user.
        db: Database session.

    Returns:
        The updated suppression rule.

    Raises:
        HTTPException: 404 if the rule does not exist.
    """
    rule = (
        db.query(AlertSuppressionRule)
        .filter(AlertSuppressionRule.id == rule_id)
        .first()
    )
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suppression rule {rule_id} not found",
        )

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    logger.info(
        "Suppression rule '%s' updated by %s", rule.name, current_user.username
    )
    return AlertSuppressionRuleResponse.model_validate(rule)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a suppression rule",
)
def delete_suppression_rule(
    rule_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Permanently delete a suppression rule.

    Args:
        rule_id: UUID of the suppression rule.
        current_user: Admin-level authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if the rule does not exist.
    """
    rule = (
        db.query(AlertSuppressionRule)
        .filter(AlertSuppressionRule.id == rule_id)
        .first()
    )
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suppression rule {rule_id} not found",
        )

    db.delete(rule)
    db.commit()
    logger.info(
        "Suppression rule '%s' deleted by %s", rule.name, current_user.username
    )


# ---------------------------------------------------------------------------
# Dry-run check
# ---------------------------------------------------------------------------


@router.post(
    "/check",
    response_model=SuppressionCheckResponse,
    summary="Dry-run: test whether given labels would be suppressed",
)
def check_suppression(
    payload: SuppressionCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuppressionCheckResponse:
    """
    Test whether an alert with the provided labels and app_id would be
    suppressed by any active rule, without actually creating an alert.

    Args:
        payload: Labels and optional app_id to test.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Whether the alert would be suppressed and which rule matched.
    """
    svc = AlertSuppressionService(db)
    matched = svc.check_suppression(
        alert_labels=payload.labels,
        app_id=payload.app_id,
    )
    if matched and matched.id is None:
        # Synthetic maintenance-mode rule has no DB representation
        return SuppressionCheckResponse(suppressed=True, matched_rule=None)
    return SuppressionCheckResponse(
        suppressed=matched is not None,
        matched_rule=(
            AlertSuppressionRuleResponse.model_validate(matched) if matched else None
        ),
    )
