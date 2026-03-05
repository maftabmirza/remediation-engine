"""
Alert Suppression Service

Checks incoming alerts against active suppression rules and returns
the first matching rule (or None when the alert should be processed
normally).

Suppression is evaluated in this order:
1. Application-level maintenance mode (immediate suppression for all
   alerts belonging to that application).
2. Active time-window + label-matcher rules (regex matching).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models_suppression import AlertSuppressionRule

logger = logging.getLogger(__name__)


class AlertSuppressionService:
    """
    Evaluates whether an incoming alert should be suppressed.

    Args:
        db: SQLAlchemy synchronous session.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_suppression(
        self,
        alert_labels: dict,
        app_id: Optional[UUID],
    ) -> Optional[AlertSuppressionRule]:
        """
        Return the first active suppression rule that matches *alert_labels*,
        or ``None`` when the alert should be processed normally.

        Args:
            alert_labels: The labels dict from the incoming alert.
            app_id: Application UUID associated with the alert (may be None).

        Returns:
            The matching ``AlertSuppressionRule`` or ``None``.
        """
        now = datetime.now(timezone.utc)

        # 1. Check application-level maintenance mode (fast path)
        if app_id is not None:
            if self._is_app_in_maintenance(app_id):
                # Create a synthetic rule object for consistent return type
                synthetic = AlertSuppressionRule(
                    name="Maintenance Mode",
                    rule_type="maintenance",
                    app_id=app_id,
                    starts_at=now,
                    is_active=True,
                )
                logger.info(
                    "Alert suppressed: application %s is in maintenance mode", app_id
                )
                return synthetic

        # 2. Fetch candidate rules from DB
        rules = self._fetch_active_rules(now)

        for rule in rules:
            # Skip rules restricted to a different application
            if rule.app_id is not None and rule.app_id != app_id:
                continue

            # Check grace period (still suppress within grace_period_minutes after window end)
            if not self._is_within_window(rule, now):
                continue

            # Check label matchers
            if self._matches_labels(rule, alert_labels):
                logger.info(
                    "Alert suppressed by rule '%s' (%s)", rule.name, rule.id
                )
                return rule

        return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_app_in_maintenance(self, app_id: UUID) -> bool:
        """Return True when the application has maintenance_mode set to True.

        Args:
            app_id: Application UUID.

        Returns:
            True if in maintenance mode, False otherwise.
        """
        try:
            from app.models_application import Application  # avoid circular at module level

            app = self.db.query(Application).filter(Application.id == app_id).first()
            if app is None:
                return False
            return bool(getattr(app, "maintenance_mode", False))
        except Exception as exc:
            logger.warning("Could not check maintenance mode for app %s: %s", app_id, exc)
            return False

    def _fetch_active_rules(self, now: datetime) -> list[AlertSuppressionRule]:
        """
        Fetch suppression rules that are currently enabled.

        Includes rules whose end time has passed but whose grace period
        has not yet elapsed.

        Args:
            now: Current UTC timestamp used to compute grace windows.

        Returns:
            List of candidate ``AlertSuppressionRule`` objects.
        """
        try:
            return (
                self.db.query(AlertSuppressionRule)
                .filter(AlertSuppressionRule.is_active.is_(True))
                .all()
            )
        except Exception as exc:
            logger.error("Failed to fetch suppression rules: %s", exc)
            return []

    def _is_within_window(self, rule: AlertSuppressionRule, now: datetime) -> bool:
        """
        Return True when *now* falls within the rule's active window,
        including the grace period.

        Args:
            rule: The suppression rule to evaluate.
            now: Current UTC timestamp.

        Returns:
            True if the rule window (plus grace) is active.
        """
        # Rule must have started
        if rule.starts_at and rule.starts_at > now:
            return False

        # Check end time + grace period
        if rule.ends_at is not None:
            grace = timedelta(minutes=rule.grace_period_minutes or 0)
            effective_end = rule.ends_at + grace
            if now > effective_end:
                return False

        return True

    def _matches_labels(self, rule: AlertSuppressionRule, alert_labels: dict) -> bool:
        """
        Return True when every matcher in *rule.matchers* matches
        the corresponding alert label value via regex.

        An empty or null matchers dict always matches (wildcard rule).

        Args:
            rule: The suppression rule containing matchers.
            alert_labels: The alert's labels dict.

        Returns:
            True when the rule matches the labels.
        """
        matchers: dict = rule.matchers or {}
        if not matchers:
            # No matchers means the rule applies to all alerts
            return True

        for label_key, pattern in matchers.items():
            label_value = str(alert_labels.get(label_key, ""))
            try:
                if not re.fullmatch(str(pattern), label_value):
                    return False
            except re.error as exc:
                logger.warning(
                    "Invalid regex pattern '%s' in rule '%s': %s",
                    pattern,
                    rule.name,
                    exc,
                )
                return False

        return True
