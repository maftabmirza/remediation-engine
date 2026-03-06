"""
OnCallService — Rotation resolution and escalation engine (Feature A1).

Extends the existing NotificationChannel → NotificationPolicy →
NotificationDispatcher architecture with on-call rotations and escalation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_oncall import (
    EscalationLevel,
    EscalationPolicy,
    OnCallOverride,
    OnCallSchedule,
)
from app.schemas_oncall import (
    EscalationContact,
    OnCallInfo,
)

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OnCallService:
    """
    Core service for on-call rotation resolution and escalation.

    All public methods accept an :class:`~sqlalchemy.ext.asyncio.AsyncSession`
    so callers can pass their existing transaction context.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Rotation resolution
    # ------------------------------------------------------------------

    async def resolve_current_oncall(
        self,
        schedule_id: UUID,
        at_time: Optional[datetime] = None,
    ) -> Optional[OnCallInfo]:
        """
        Resolve who is currently on-call for a given schedule.

        Algorithm:
        1. Check active overrides (highest priority).
        2. Calculate rotation position from effective_from date.
        3. Respect handoff_time (DST-safe via zoneinfo/pytz).

        Args:
            schedule_id: UUID of the OnCallSchedule.
            at_time: Point in time to resolve (defaults to now UTC).

        Returns:
            OnCallInfo for the primary on-call person, or None if no participants.
        """
        at_time = at_time or _utc_now()

        # 1. Check for an active override
        override = await self._find_active_override(schedule_id, at_time)
        if override is not None:
            from app.models import User  # noqa: PLC0415

            user = await self.db.get(User, override.override_user_id)
            if user is None:
                logger.warning(
                    "Override %s references unknown user %s",
                    override.id,
                    override.override_user_id,
                )
            else:
                schedule = await self.db.get(OnCallSchedule, schedule_id)
                return OnCallInfo(
                    user_id=user.id,
                    user_name=user.full_name or user.username,
                    user_email=user.email or "",
                    role="primary",
                    schedule_id=schedule_id,
                    schedule_name=schedule.name if schedule else "",
                    is_override=True,
                    escalation_level=1,
                    escalates_in_minutes=None,
                )

        # 2. Load schedule
        schedule = await self.db.get(OnCallSchedule, schedule_id)
        if schedule is None or not schedule.is_active:
            return None

        participants = list(schedule.participants or [])
        if not participants:
            return None

        # 3. Determine participant index via rotation
        participant_index = self._calculate_rotation_index(schedule, at_time)
        participant = participants[participant_index % len(participants)]

        user_id_str = participant.get("user_id")
        if not user_id_str:
            return None

        from app.models import User  # noqa: PLC0415

        user = await self.db.get(User, UUID(str(user_id_str)))
        if user is None:
            logger.warning("On-call participant user %s not found", user_id_str)
            return None

        return OnCallInfo(
            user_id=user.id,
            user_name=user.full_name or user.username,
            user_email=user.email or "",
            role=participant.get("role", "primary"),
            schedule_id=schedule_id,
            schedule_name=schedule.name,
            is_override=False,
            escalation_level=1,
            escalates_in_minutes=None,
        )

    async def resolve_for_app(
        self,
        app_id: UUID,
    ) -> List[EscalationContact]:
        """
        Resolve the full escalation chain for an application.

        Args:
            app_id: UUID of the application.

        Returns:
            Ordered list of EscalationContact (level 1 first).
        """
        policy = await self._find_policy_for_app(app_id)
        if policy is None:
            return []

        contacts: List[EscalationContact] = []
        for level in sorted(policy.levels, key=lambda lvl: lvl.level_number):
            oncall_info = await self._resolve_level_contact(level)
            if oncall_info is None:
                continue

            oncall_info.escalation_level = level.level_number
            oncall_info.escalates_in_minutes = level.timeout_minutes

            channel_pref = await self._select_channel_preference(level)

            contacts.append(
                EscalationContact(
                    level=level.level_number,
                    user=oncall_info,
                    channel_preference=channel_pref,
                    timeout_minutes=level.timeout_minutes,
                    policy_id=policy.id,
                )
            )

        return contacts

    async def get_current_oncall(
        self,
        group_id: Optional[UUID] = None,
        app_id: Optional[UUID] = None,
    ) -> List[OnCallInfo]:
        """
        "Who is on-call right now?" — for UI, API, and AI agents.

        Args:
            group_id: Return on-call info for all active schedules of this group.
            app_id: Return escalation chain for this application.

        Returns:
            List of OnCallInfo objects, ordered by escalation level.
        """
        if app_id is not None:
            contacts = await self.resolve_for_app(app_id)
            return [c.user for c in contacts]

        # Query by group or return all active schedules
        stmt = select(OnCallSchedule).where(OnCallSchedule.is_active.is_(True))
        if group_id is not None:
            stmt = stmt.where(OnCallSchedule.group_id == group_id)

        result = await self.db.execute(stmt)
        schedules = result.scalars().all()

        oncall_list: List[OnCallInfo] = []
        for schedule in schedules:
            info = await self.resolve_current_oncall(schedule.id)
            if info is not None:
                oncall_list.append(info)

        return oncall_list

    async def escalate(
        self,
        alert_id: UUID,
        current_level: int,
        policy_id: UUID,
    ) -> bool:
        """
        Escalate an unacknowledged alert to the next level.

        Called by APScheduler when the ack timeout for a level expires.

        Args:
            alert_id: UUID of the Alert.
            current_level: The level that timed out.
            policy_id: UUID of the EscalationPolicy.

        Returns:
            True if escalated to next level, False if all levels exhausted.
        """
        policy = await self.db.get(EscalationPolicy, policy_id)
        if policy is None:
            logger.warning("EscalationPolicy %s not found for alert %s", policy_id, alert_id)
            return False

        levels = sorted(policy.levels, key=lambda lvl: lvl.level_number)
        next_levels = [lvl for lvl in levels if lvl.level_number > current_level]

        if next_levels:
            next_level = next_levels[0]
            oncall_info = await self._resolve_level_contact(next_level)
            if oncall_info is None:
                logger.warning(
                    "Could not resolve on-call for level %d of policy %s",
                    next_level.level_number,
                    policy_id,
                )
                return False

            await self._send_escalation_notification(alert_id, oncall_info, next_level)
            await self._schedule_next_escalation(alert_id, policy_id, next_level)
            logger.info(
                "Alert %s escalated to level %d (user=%s)",
                alert_id,
                next_level.level_number,
                oncall_info.user_id,
            )
            return True

        # All levels exhausted — check repeat_count
        if policy.repeat_count > 0:
            logger.info(
                "Alert %s: all levels exhausted, cycling (repeat_count=%d)",
                alert_id,
                policy.repeat_count,
            )
            # Cycle back to level 1 by recursing with current_level = 0
            return await self.escalate(alert_id, 0, policy_id)

        logger.warning(
            "Alert %s: escalation exhausted for policy %s — all levels notified",
            alert_id,
            policy_id,
        )
        return False

    # ------------------------------------------------------------------
    # Timeline generation
    # ------------------------------------------------------------------

    async def get_schedule_timeline(
        self,
        schedule_id: UUID,
        days: int = 30,
    ) -> list:
        """
        Generate the upcoming rotation timeline for a schedule.

        Args:
            schedule_id: UUID of the OnCallSchedule.
            days: Number of days ahead to generate.

        Returns:
            List of OnCallTimelineEntry dicts (as plain dicts for flexibility).
        """
        from datetime import timedelta  # noqa: PLC0415

        from app.models import User  # noqa: PLC0415
        from app.schemas_oncall import OnCallTimelineEntry  # noqa: PLC0415

        schedule = await self.db.get(OnCallSchedule, schedule_id)
        if schedule is None or not schedule.participants:
            return []

        participants = list(schedule.participants)
        timeline = []
        now = _utc_now()

        # Fetch user info for all participants once
        user_map: dict = {}
        for p in participants:
            uid = p.get("user_id")
            if uid:
                user = await self.db.get(User, UUID(str(uid)))
                if user:
                    user_map[str(uid)] = user.full_name or user.username

        # Fetch overrides for the window
        window_end = now + timedelta(days=days)
        override_result = await self.db.execute(
            select(OnCallOverride)
            .where(
                and_(
                    OnCallOverride.schedule_id == schedule_id,
                    OnCallOverride.ends_at >= now,
                    OnCallOverride.starts_at <= window_end,
                )
            )
            .order_by(OnCallOverride.starts_at)
        )
        overrides = override_result.scalars().all()

        # Build a day-by-day timeline
        current = now
        step = timedelta(days=1) if schedule.rotation_type == "daily" else timedelta(weeks=1)
        while current < window_end:
            slot_end = min(current + step, window_end)

            # Check for override
            active_override = None
            for ov in overrides:
                if ov.starts_at <= current < ov.ends_at:
                    active_override = ov
                    break

            if active_override:
                ov_user = await self.db.get(User, active_override.override_user_id)
                timeline.append(
                    OnCallTimelineEntry(
                        starts_at=current,
                        ends_at=slot_end,
                        user_id=active_override.override_user_id,
                        user_name=ov_user.full_name or ov_user.username if ov_user else "",
                        is_override=True,
                    )
                )
            else:
                idx = self._calculate_rotation_index(schedule, current)
                p = participants[idx % len(participants)]
                uid = str(p.get("user_id", ""))
                timeline.append(
                    OnCallTimelineEntry(
                        starts_at=current,
                        ends_at=slot_end,
                        user_id=UUID(uid) if uid else UUID(int=0),
                        user_name=user_map.get(uid, "Unknown"),
                        is_override=False,
                    )
                )

            current = slot_end

        return timeline

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calculate_rotation_index(
        self,
        schedule: OnCallSchedule,
        at_time: datetime,
    ) -> int:
        """
        Calculate the zero-based participant index for ``at_time``.

        Handles daily and weekly rotation types, handoff_time, and DST.
        """
        try:
            try:
                from zoneinfo import ZoneInfo  # Python 3.9+
                tz = ZoneInfo(schedule.timezone)
            except ImportError:
                import pytz  # noqa: PLC0415
                tz = pytz.timezone(schedule.timezone)

            # Convert both times to the schedule's local timezone (DST-safe)
            local_at = at_time.astimezone(tz)
            effective_from = schedule.effective_from.astimezone(tz)

            # Determine handoff_time (time object from the DB, default 09:00)
            handoff = schedule.handoff_time
            if handoff is None:
                from datetime import time as _time  # noqa: PLC0415
                handoff = _time(9, 0)

            # Adjust for handoff: if before handoff_time on current day, use previous slot
            local_date = local_at.date()
            if local_at.time() < handoff:
                from datetime import timedelta as _td  # noqa: PLC0415
                local_date = local_date - _td(days=1)

            effective_date = effective_from.date()
            days_elapsed = (local_date - effective_date).days
            if days_elapsed < 0:
                days_elapsed = 0

            participants = list(schedule.participants or [])
            if not participants:
                return 0

            if schedule.rotation_type == "weekly":
                weeks_elapsed = days_elapsed // 7
                return weeks_elapsed % len(participants)
            else:
                # daily (and custom falls back to daily)
                return days_elapsed % len(participants)

        except Exception as exc:
            logger.warning("Rotation index calculation failed: %s", exc)
            return 0

    async def _find_active_override(
        self,
        schedule_id: UUID,
        at_time: datetime,
    ) -> Optional[OnCallOverride]:
        """Return the active override for a schedule at a given time, if any."""
        result = await self.db.execute(
            select(OnCallOverride)
            .where(
                and_(
                    OnCallOverride.schedule_id == schedule_id,
                    OnCallOverride.starts_at <= at_time,
                    OnCallOverride.ends_at >= at_time,
                )
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _find_policy_for_app(
        self,
        app_id: UUID,
    ) -> Optional[EscalationPolicy]:
        """Find the best matching escalation policy for an application."""
        # App-specific policy first
        result = await self.db.execute(
            select(EscalationPolicy).where(
                and_(
                    EscalationPolicy.app_id == app_id,
                    EscalationPolicy.is_active.is_(True),
                )
            )
        )
        policy = result.scalar_one_or_none()
        if policy is not None:
            return policy

        # Fall back to default policy
        result = await self.db.execute(
            select(EscalationPolicy).where(
                and_(
                    EscalationPolicy.is_default.is_(True),
                    EscalationPolicy.is_active.is_(True),
                )
            )
        )
        return result.scalar_one_or_none()

    async def _resolve_level_contact(
        self,
        level: EscalationLevel,
    ) -> Optional[OnCallInfo]:
        """Resolve the on-call contact for a given escalation level."""
        from app.models import User  # noqa: PLC0415

        if level.schedule_id is not None:
            return await self.resolve_current_oncall(level.schedule_id)

        if level.user_id is not None:
            user = await self.db.get(User, level.user_id)
            if user is None:
                return None
            # We need a valid schedule_id for OnCallInfo; use a sentinel
            return OnCallInfo(
                user_id=user.id,
                user_name=user.full_name or user.username,
                user_email=user.email or "",
                role="primary",
                schedule_id=UUID(int=0),
                schedule_name="direct",
                is_override=False,
                escalation_level=level.level_number,
                escalates_in_minutes=level.timeout_minutes,
            )

        return None

    async def _select_channel_preference(self, level: EscalationLevel) -> str:
        """
        Select the preferred channel type for a level.

        If a channel is explicitly set on the level, return its type.
        Otherwise returns "email" as the default delivery method.
        Note: SMS/phone channels are not natively supported; high-urgency
        alerts should use explicit channel_id overrides on the level.
        """
        if level.channel_id is not None:
            from app.models_notification import NotificationChannel  # noqa: PLC0415

            channel = await self.db.get(NotificationChannel, level.channel_id)
            if channel is not None:
                return channel.channel_type

        # Default by urgency: high → slack (faster), low → email
        return "slack" if level.urgency == "high" else "email"

    async def _send_escalation_notification(
        self,
        alert_id: UUID,
        oncall_info: OnCallInfo,
        level: EscalationLevel,
    ) -> None:
        """Send immediate escalation notification for an alert."""
        try:
            from app.database import async_session_factory  # noqa: PLC0415
            from app.services.notification.service import NotificationService  # noqa: PLC0415

            async with async_session_factory() as db:
                svc = NotificationService(db)
                await svc.notify(
                    "alert.escalation",
                    {
                        "alert_id": str(alert_id),
                        "escalation_level": level.level_number,
                        "oncall_user": oncall_info.user_name,
                        "oncall_email": oncall_info.user_email,
                    },
                    event_id=alert_id,
                )
        except Exception as exc:
            logger.exception(
                "Failed to send escalation notification for alert %s: %s", alert_id, exc
            )

    async def _schedule_next_escalation(
        self,
        alert_id: UUID,
        policy_id: UUID,
        level: EscalationLevel,
    ) -> None:
        """Schedule the next escalation timeout via APScheduler."""
        try:
            from datetime import timedelta  # noqa: PLC0415

            from apscheduler.triggers.date import DateTrigger  # noqa: PLC0415

            from app.services.scheduler_service import get_scheduler  # noqa: PLC0415

            scheduler = get_scheduler()
            run_at = _utc_now() + timedelta(minutes=level.timeout_minutes)
            job_id = f"escalation_{alert_id}_{level.level_number}"

            scheduler._scheduler.add_job(
                func=_run_escalation,
                trigger=DateTrigger(run_date=run_at),
                id=job_id,
                replace_existing=True,
                kwargs={
                    "alert_id": str(alert_id),
                    "current_level": level.level_number,
                    "policy_id": str(policy_id),
                },
            )
            logger.info(
                "Scheduled escalation job %s at %s for alert %s",
                job_id,
                run_at,
                alert_id,
            )
        except Exception as exc:
            logger.exception(
                "Failed to schedule escalation for alert %s level %d: %s",
                alert_id,
                level.level_number,
                exc,
            )


# ---------------------------------------------------------------------------
# APScheduler callback (module-level, must be serialisable)
# ---------------------------------------------------------------------------


async def _run_escalation(
    alert_id: str,
    current_level: int,
    policy_id: str,
) -> None:
    """
    APScheduler callback — escalate an alert to the next level.

    This is a module-level function so it can be pickled by APScheduler.
    """
    from app.database import async_session_factory  # noqa: PLC0415

    async with async_session_factory() as db:
        svc = OnCallService(db)
        await svc.escalate(
            alert_id=UUID(alert_id),
            current_level=current_level,
            policy_id=UUID(policy_id),
        )
