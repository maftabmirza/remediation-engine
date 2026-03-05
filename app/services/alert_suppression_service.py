"""
Alert Suppression Service (Feature A6)

Provides create/read/update/delete operations for alert suppression rules and
a fast check function used by the webhook to determine whether an incoming
alert should be suppressed.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models import AlertSuppressionRule
from app.services.rules_engine import match_pattern

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Return current UTC time (thin wrapper for test-time patching)."""
    return datetime.now(timezone.utc)


class AlertSuppressionService:
    """
    Manages alert suppression rules and evaluates incoming alerts against them.

    A suppression rule silences alerts that match all of the following patterns:
      - alert_name_pattern
      - severity_pattern
      - instance_pattern
      - job_pattern

    Rules can optionally be limited to a time window (starts_at / ends_at).
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def check_suppressed(
        self,
        alert_name: str,
        severity: str,
        instance: str,
        job: str,
    ) -> Tuple[bool, Optional[AlertSuppressionRule]]:
        """
        Check whether an incoming alert matches any active suppression rule.

        Args:
            alert_name: The name of the alert (e.g. "HighCPUUsage").
            severity:   Severity label (e.g. "critical", "warning").
            instance:   Instance label (e.g. "web-01:9100").
            job:        Job/service label (e.g. "node-exporter").

        Returns:
            A tuple of (suppressed, matching_rule).
            ``suppressed`` is True when the alert should be silenced.
            ``matching_rule`` is the first matching rule, or None.
        """
        now = _utc_now()

        # Fetch all active rules in one query — suppression tables are typically
        # small so loading them all is acceptable.
        rules: List[AlertSuppressionRule] = (
            self.db.query(AlertSuppressionRule)
            .filter(AlertSuppressionRule.is_active.is_(True))
            .all()
        )

        for rule in rules:
            # Check time window constraints
            if rule.starts_at and now < rule.starts_at:
                continue
            if rule.ends_at and now > rule.ends_at:
                continue

            # Check pattern match (all four patterns must match)
            if (
                match_pattern(rule.alert_name_pattern or "*", alert_name)
                and match_pattern(rule.severity_pattern or "*", severity)
                and match_pattern(rule.instance_pattern or "*", instance)
                and match_pattern(rule.job_pattern or "*", job)
            ):
                logger.info(
                    "Alert '%s' suppressed by rule '%s' (id=%s)",
                    alert_name,
                    rule.name,
                    rule.id,
                )
                return True, rule

        return False, None

    def list_rules(
        self,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = False,
    ) -> Tuple[List[AlertSuppressionRule], int]:
        """
        Return a paginated list of suppression rules.

        Args:
            page:        1-based page number.
            page_size:   Records per page (max 100).
            active_only: When True, only return currently active rules.

        Returns:
            Tuple of (rules_list, total_count).
        """
        page_size = min(page_size, 100)
        query = self.db.query(AlertSuppressionRule)
        if active_only:
            query = query.filter(AlertSuppressionRule.is_active.is_(True))
        total = query.count()
        rules = (
            query.order_by(AlertSuppressionRule.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return rules, total

    def get_rule(self, rule_id: UUID) -> Optional[AlertSuppressionRule]:
        """
        Retrieve a single suppression rule by its ID.

        Args:
            rule_id: UUID of the rule.

        Returns:
            The rule, or None if not found.
        """
        return (
            self.db.query(AlertSuppressionRule)
            .filter(AlertSuppressionRule.id == rule_id)
            .first()
        )

    def create_rule(
        self,
        name: str,
        description: Optional[str],
        alert_name_pattern: str,
        severity_pattern: str,
        instance_pattern: str,
        job_pattern: str,
        starts_at: Optional[datetime],
        ends_at: Optional[datetime],
        is_active: bool,
        reason: Optional[str],
        created_by: Optional[UUID],
    ) -> AlertSuppressionRule:
        """
        Create and persist a new suppression rule.

        Args:
            name:                Human-readable rule name.
            description:         Optional description.
            alert_name_pattern:  Wildcard pattern for the alert name.
            severity_pattern:    Wildcard pattern for the severity label.
            instance_pattern:    Wildcard pattern for the instance label.
            job_pattern:         Wildcard pattern for the job label.
            starts_at:           Optional window start (UTC).
            ends_at:             Optional window end (UTC).
            is_active:           Whether the rule is immediately active.
            reason:              Human-readable reason for the suppression.
            created_by:          UUID of the user creating the rule.

        Returns:
            The newly created rule.

        Raises:
            ValueError: If ends_at is before starts_at.
        """
        if starts_at and ends_at and ends_at <= starts_at:
            raise ValueError("ends_at must be after starts_at")

        rule = AlertSuppressionRule(
            name=name,
            description=description,
            alert_name_pattern=alert_name_pattern,
            severity_pattern=severity_pattern,
            instance_pattern=instance_pattern,
            job_pattern=job_pattern,
            starts_at=starts_at,
            ends_at=ends_at,
            is_active=is_active,
            reason=reason,
            created_by=created_by,
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        logger.info("Created suppression rule '%s' (id=%s)", rule.name, rule.id)
        return rule

    def update_rule(
        self,
        rule_id: UUID,
        updates: dict,
    ) -> Optional[AlertSuppressionRule]:
        """
        Partially update an existing suppression rule.

        Args:
            rule_id: UUID of the rule to update.
            updates: Dictionary of field-name → new-value pairs.

        Returns:
            The updated rule, or None if the rule was not found.

        Raises:
            ValueError: If the updated ends_at/starts_at window is invalid.
        """
        rule = self.get_rule(rule_id)
        if not rule:
            return None

        for field, value in updates.items():
            setattr(rule, field, value)

        # Re-validate time window after applying updates
        if rule.starts_at and rule.ends_at and rule.ends_at <= rule.starts_at:
            raise ValueError("ends_at must be after starts_at")

        self.db.commit()
        self.db.refresh(rule)
        logger.info("Updated suppression rule '%s' (id=%s)", rule.name, rule.id)
        return rule

    def delete_rule(self, rule_id: UUID) -> bool:
        """
        Delete a suppression rule.

        Args:
            rule_id: UUID of the rule to delete.

        Returns:
            True if the rule was found and deleted, False otherwise.
        """
        rule = self.get_rule(rule_id)
        if not rule:
            return False
        self.db.delete(rule)
        self.db.commit()
        logger.info("Deleted suppression rule id=%s", rule_id)
        return True
