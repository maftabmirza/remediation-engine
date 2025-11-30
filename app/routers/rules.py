"""
Rules API endpoints
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import asc

from app.database import get_db
from app.models import AutoAnalyzeRule, User, AuditLog
from app.schemas import (
    RuleCreate, RuleUpdate, RuleResponse,
    RuleTestRequest, RuleTestResponse
)
from app.services.auth_service import get_current_user, require_admin
from app.services.rules_engine import test_rules

router = APIRouter(prefix="/api/rules", tags=["Rules"])


@router.get("", response_model=List[RuleResponse])
async def list_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all auto-analyze rules ordered by priority.
    """
    rules = db.query(AutoAnalyzeRule).order_by(asc(AutoAnalyzeRule.priority)).all()
    return [RuleResponse.model_validate(r) for r in rules]


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    request: Request,
    rule_data: RuleCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new auto-analyze rule. Admin only.
    """
    # Validate action
    if rule_data.action not in ["auto_analyze", "ignore", "manual"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be one of: auto_analyze, ignore, manual"
        )
    
    rule = AutoAnalyzeRule(
        name=rule_data.name,
        description=rule_data.description,
        priority=rule_data.priority,
        alert_name_pattern=rule_data.alert_name_pattern,
        severity_pattern=rule_data.severity_pattern,
        instance_pattern=rule_data.instance_pattern,
        job_pattern=rule_data.job_pattern,
        action=rule_data.action,
        enabled=rule_data.enabled,
        created_by=current_user.id
    )
    
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="create_rule",
        resource_type="rule",
        resource_id=rule.id,
        details_json={"name": rule.name, "action": rule.action},
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    db.commit()
    
    return RuleResponse.model_validate(rule)


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific rule by ID.
    """
    rule = db.query(AutoAnalyzeRule).filter(AutoAnalyzeRule.id == rule_id).first()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )
    
    return RuleResponse.model_validate(rule)


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: UUID,
    request: Request,
    rule_data: RuleUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update an existing rule. Admin only.
    """
    rule = db.query(AutoAnalyzeRule).filter(AutoAnalyzeRule.id == rule_id).first()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )
    
    # Update only provided fields
    update_data = rule_data.model_dump(exclude_unset=True)
    
    # Validate action if provided
    if "action" in update_data and update_data["action"] not in ["auto_analyze", "ignore", "manual"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be one of: auto_analyze, ignore, manual"
        )
    
    for field, value in update_data.items():
        setattr(rule, field, value)
    
    db.commit()
    db.refresh(rule)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="update_rule",
        resource_type="rule",
        resource_id=rule.id,
        details_json={"updated_fields": list(update_data.keys())},
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    db.commit()
    
    return RuleResponse.model_validate(rule)


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete a rule. Admin only.
    """
    rule = db.query(AutoAnalyzeRule).filter(AutoAnalyzeRule.id == rule_id).first()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="delete_rule",
        resource_type="rule",
        resource_id=rule.id,
        details_json={"name": rule.name},
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    
    db.delete(rule)
    db.commit()
    
    return {"message": "Rule deleted successfully"}


@router.post("/test", response_model=RuleTestResponse)
async def test_rule_matching(
    test_data: RuleTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test which rule would match for given alert parameters.
    Useful for debugging rule configurations.
    """
    result = test_rules(
        db,
        test_data.alert_name,
        test_data.severity,
        test_data.instance,
        test_data.job
    )
    
    return RuleTestResponse(
        matched_rule=RuleResponse.model_validate(result["matched_rule"]) if result["matched_rule"] else None,
        action=result["action"],
        message=result["message"]
    )


@router.post("/{rule_id}/toggle")
async def toggle_rule(
    rule_id: UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Toggle a rule's enabled status. Admin only.
    """
    rule = db.query(AutoAnalyzeRule).filter(AutoAnalyzeRule.id == rule_id).first()
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found"
        )
    
    rule.enabled = not rule.enabled
    db.commit()
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="toggle_rule",
        resource_type="rule",
        resource_id=rule.id,
        details_json={"name": rule.name, "enabled": rule.enabled},
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    db.commit()
    
    return {"message": f"Rule {'enabled' if rule.enabled else 'disabled'}", "enabled": rule.enabled}
