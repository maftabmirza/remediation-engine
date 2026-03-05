"""
Unit tests for OnCallService (Feature A1).

Covers: rotation resolution, override priority, escalation engine,
        channel preference selection, and get_current_oncall.
"""

from __future__ import annotations

import pytest
from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc(offset_minutes: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)


def _utc_date(offset_days: int = 0) -> datetime:
    base = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
    return base + timedelta(days=offset_days)


def _make_user(name: str = "alice", email: str = "alice@example.com") -> MagicMock:
    u = MagicMock()
    u.id = uuid4()
    u.username = name
    u.full_name = name.capitalize()
    u.email = email
    return u


def _make_schedule(
    rotation_type: str = "daily",
    participants=None,
    handoff_time=None,
    effective_from=None,
    is_active: bool = True,
    timezone: str = "UTC",
) -> MagicMock:
    s = MagicMock()
    s.id = uuid4()
    s.name = "test-schedule"
    s.rotation_type = rotation_type
    # Use is None check so empty list is preserved
    if participants is None:
        s.participants = [
            {"user_id": str(uuid4()), "order": 1, "role": "primary"},
            {"user_id": str(uuid4()), "order": 2, "role": "secondary"},
        ]
    else:
        s.participants = participants
    s.handoff_time = handoff_time or time(9, 0)
    s.effective_from = effective_from or _utc_date(-30)
    s.effective_until = None
    s.is_active = is_active
    s.timezone = timezone
    return s


def _make_override(
    schedule_id=None,
    override_user_id=None,
    starts_at=None,
    ends_at=None,
) -> MagicMock:
    ov = MagicMock()
    ov.id = uuid4()
    ov.schedule_id = schedule_id or uuid4()
    ov.override_user_id = override_user_id or uuid4()
    ov.starts_at = starts_at or _utc(-60)
    ov.ends_at = ends_at or _utc(60)
    return ov


def _make_policy(
    is_default: bool = False,
    is_active: bool = True,
    repeat_count: int = 0,
    app_id=None,
) -> MagicMock:
    p = MagicMock()
    p.id = uuid4()
    p.name = "test-policy"
    p.is_default = is_default
    p.is_active = is_active
    p.repeat_count = repeat_count
    p.app_id = app_id or uuid4()
    p.levels = []
    return p


def _make_level(
    level_number: int = 1,
    schedule_id=None,
    user_id=None,
    channel_id=None,
    timeout_minutes: int = 30,
    urgency: str = "high",
    policy_id=None,
) -> MagicMock:
    lvl = MagicMock()
    lvl.id = uuid4()
    lvl.level_number = level_number
    lvl.schedule_id = schedule_id
    lvl.user_id = user_id
    lvl.channel_id = channel_id
    lvl.timeout_minutes = timeout_minutes
    lvl.urgency = urgency
    lvl.policy_id = policy_id or uuid4()
    lvl.notification_steps = []
    return lvl


def _make_service() -> tuple:
    """Return (OnCallService, AsyncMock db)."""
    from app.services.oncall_service import OnCallService

    db = AsyncMock()
    svc = OnCallService(db)
    return svc, db


def _scalar_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _scalars_result(values):
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


# ===========================================================================
# Rotation index calculation (unit tests for _calculate_rotation_index)
# ===========================================================================

@pytest.mark.unit
class TestCalculateRotationIndex:
    """Tests for OnCallService._calculate_rotation_index."""

    def _get_method(self):
        from app.services.oncall_service import OnCallService

        db = AsyncMock()
        return OnCallService(db)._calculate_rotation_index

    def test_daily_rotation_day_0(self):
        """Day 0 (effective_from date) → index 0."""
        calc = self._get_method()
        effective = _utc_date(0).replace(hour=12)  # noon
        schedule = _make_schedule(
            rotation_type="daily",
            participants=[{"user_id": str(uuid4())}, {"user_id": str(uuid4())}],
            handoff_time=time(9, 0),
            effective_from=effective,
        )
        at_time = effective.replace(hour=10)
        idx = calc(schedule, at_time)
        assert idx == 0

    def test_daily_rotation_day_n(self):
        """Day N → index = N % len(participants)."""
        calc = self._get_method()
        participants = [{"user_id": str(uuid4())} for _ in range(3)]
        effective = _utc_date(-10).replace(hour=9, minute=0)
        schedule = _make_schedule(
            rotation_type="daily",
            participants=participants,
            handoff_time=time(9, 0),
            effective_from=effective,
        )
        # 7 days after → index = 7 % 3 = 1
        at_time = effective + timedelta(days=7, hours=1)
        idx = calc(schedule, at_time)
        assert idx == 7 % 3

    def test_weekly_rotation(self):
        """Weekly: weeks_elapsed // 1 used, correct participant selected."""
        calc = self._get_method()
        participants = [{"user_id": str(uuid4())} for _ in range(4)]
        effective = _utc_date(-21).replace(hour=9, minute=0)
        schedule = _make_schedule(
            rotation_type="weekly",
            participants=participants,
            handoff_time=time(9, 0),
            effective_from=effective,
        )
        # 14 days = 2 full weeks → index = 2 % 4 = 2
        at_time = effective + timedelta(days=14, hours=1)
        idx = calc(schedule, at_time)
        assert idx == 2

    def test_handoff_time_before_handoff_uses_previous_day(self):
        """At 08:59 UTC (before 09:00 handoff) → use yesterday's assignment."""
        calc = self._get_method()
        participants = [{"user_id": str(uuid4())} for _ in range(3)]
        # effective_from is day 0 at 09:00 UTC
        effective = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
        schedule = _make_schedule(
            rotation_type="daily",
            participants=participants,
            handoff_time=time(9, 0),
            effective_from=effective,
        )
        # Day 3 at 08:59 → should use day 2 assignment
        at_time = datetime(2026, 3, 4, 8, 59, tzinfo=timezone.utc)  # day 3, before handoff
        idx = calc(schedule, at_time)
        # days_elapsed would be 2 (day 3 - 1 = day 2), 2 % 3 = 2
        assert idx == 2

    def test_handoff_time_after_handoff_uses_current_day(self):
        """At 09:01 UTC (after 09:00 handoff) → use today's assignment."""
        calc = self._get_method()
        participants = [{"user_id": str(uuid4())} for _ in range(3)]
        effective = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
        schedule = _make_schedule(
            rotation_type="daily",
            participants=participants,
            handoff_time=time(9, 0),
            effective_from=effective,
        )
        # Day 3 at 09:01 → use day 3 assignment: 3 % 3 = 0
        at_time = datetime(2026, 3, 4, 9, 1, tzinfo=timezone.utc)
        idx = calc(schedule, at_time)
        assert idx == 0

    def test_empty_participants_returns_zero(self):
        """Empty participants list → index 0 (caller handles None check)."""
        calc = self._get_method()
        schedule = _make_schedule(participants=[])
        idx = calc(schedule, _utc_now())
        assert idx == 0

    def test_negative_days_clamped_to_zero(self):
        """at_time before effective_from → clamp to index 0."""
        calc = self._get_method()
        participants = [{"user_id": str(uuid4())} for _ in range(2)]
        # effective_from is a fixed future date
        effective = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        schedule = _make_schedule(
            rotation_type="daily",
            participants=participants,
            effective_from=effective,
        )
        # at_time is before effective_from → negative days_elapsed → clamped to 0
        at_time = datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc)
        idx = calc(schedule, at_time)
        assert idx == 0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ===========================================================================
# resolve_current_oncall — rotation resolution
# ===========================================================================

@pytest.mark.unit
class TestResolveCurrentOncall:
    """Tests for OnCallService.resolve_current_oncall."""

    @pytest.mark.asyncio
    async def test_returns_none_when_schedule_not_found(self):
        """Returns None when schedule does not exist."""
        svc, db = _make_service()
        db.get = AsyncMock(return_value=None)
        db.execute = AsyncMock(return_value=_scalar_result(None))  # no override

        result = await svc.resolve_current_oncall(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_inactive_schedule(self):
        """Returns None for an inactive schedule."""
        svc, db = _make_service()
        schedule = _make_schedule(is_active=False)

        # No override, then return inactive schedule
        db.execute = AsyncMock(return_value=_scalar_result(None))
        db.get = AsyncMock(return_value=schedule)

        result = await svc.resolve_current_oncall(schedule.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_participants(self):
        """Returns None when schedule has no participants."""
        svc, db = _make_service()
        schedule = _make_schedule(participants=[])

        db.execute = AsyncMock(return_value=_scalar_result(None))
        db.get = AsyncMock(return_value=schedule)

        result = await svc.resolve_current_oncall(schedule.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_override_priority_active(self):
        """Active override → override_user returned (not rotation user)."""
        svc, db = _make_service()
        override_user = _make_user("bob", "bob@example.com")
        override = _make_override(override_user_id=override_user.id)
        schedule = _make_schedule()

        # execute() returns override; get() returns override_user then schedule
        db.execute = AsyncMock(return_value=_scalar_result(override))
        db.get = AsyncMock(side_effect=[override_user, schedule])

        result = await svc.resolve_current_oncall(schedule.id)
        assert result is not None
        assert result.user_id == override_user.id
        assert result.is_override is True

    @pytest.mark.asyncio
    async def test_override_not_yet_active_uses_rotation(self):
        """Override starts_at is in the future → rotation user returned."""
        svc, db = _make_service()
        user = _make_user("alice")
        participant_id = uuid4()
        schedule = _make_schedule(
            participants=[{"user_id": str(participant_id), "order": 1, "role": "primary"}],
            effective_from=_utc_date(-5),
        )

        # No active override (starts in future)
        db.execute = AsyncMock(return_value=_scalar_result(None))
        db.get = AsyncMock(side_effect=[schedule, user])

        result = await svc.resolve_current_oncall(schedule.id)
        # Should succeed with rotation user (user returned by db.get)
        assert result is not None
        assert result.is_override is False

    @pytest.mark.asyncio
    async def test_override_expired_uses_rotation(self):
        """Override ends_at is in the past → rotation user returned."""
        svc, db = _make_service()
        user = _make_user("carol")
        participant_id = uuid4()
        schedule = _make_schedule(
            participants=[{"user_id": str(participant_id), "order": 1, "role": "primary"}],
            effective_from=_utc_date(-10),
        )

        # No current override
        db.execute = AsyncMock(return_value=_scalar_result(None))
        db.get = AsyncMock(side_effect=[schedule, user])

        result = await svc.resolve_current_oncall(schedule.id)
        assert result is not None
        assert result.is_override is False

    @pytest.mark.asyncio
    async def test_daily_rotation_returns_correct_user(self):
        """Daily rotation: participant at computed index is returned."""
        svc, db = _make_service()
        user_a = _make_user("alice", "alice@example.com")
        user_b = _make_user("bob", "bob@example.com")

        pid_a = uuid4()
        pid_b = uuid4()
        participants = [
            {"user_id": str(pid_a), "order": 1, "role": "primary"},
            {"user_id": str(pid_b), "order": 2, "role": "secondary"},
        ]
        # Effective from 1 day ago → day 1 → index = 1 → user_b
        effective = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
        schedule = _make_schedule(
            participants=participants,
            effective_from=effective,
        )

        db.execute = AsyncMock(return_value=_scalar_result(None))  # no override
        # at 1 day + 1 hour after effective → day 1 → participant index 1 → user_b
        at_time = datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc)

        db.get = AsyncMock(side_effect=[schedule, user_b])

        result = await svc.resolve_current_oncall(schedule.id, at_time=at_time)
        assert result is not None
        assert result.user_id == user_b.id
        assert result.user_name == "Bob"


# ===========================================================================
# resolve_for_app — escalation chain resolution
# ===========================================================================

@pytest.mark.unit
class TestResolveForApp:
    """Tests for OnCallService.resolve_for_app."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_policy(self):
        """Returns empty list when no app-specific or default policy exists."""
        svc, db = _make_service()
        # Both app-specific and default queries return None
        db.execute = AsyncMock(side_effect=[
            _scalar_result(None),  # app-specific policy
            _scalar_result(None),  # default policy
        ])

        result = await svc.resolve_for_app(uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_falls_back_to_default_policy(self):
        """Falls back to default policy when no app-specific policy exists."""
        svc, db = _make_service()
        user = _make_user("dave", "dave@example.com")
        policy = _make_policy(is_default=True)
        level = _make_level(level_number=1, user_id=user.id, policy_id=policy.id)
        policy.levels = [level]

        db.execute = AsyncMock(side_effect=[
            _scalar_result(None),    # no app-specific policy
            _scalar_result(policy),  # default policy
            _scalar_result(None),    # no override for level (if schedule_id)
        ])
        db.get = AsyncMock(return_value=user)

        result = await svc.resolve_for_app(uuid4())
        assert len(result) == 1
        assert result[0].level == 1
        assert result[0].user.user_id == user.id

    @pytest.mark.asyncio
    async def test_app_specific_policy_takes_precedence(self):
        """App-specific policy is used over default policy."""
        svc, db = _make_service()
        app_id = uuid4()
        user = _make_user("eve", "eve@example.com")
        policy = _make_policy(app_id=app_id)
        level = _make_level(level_number=1, user_id=user.id, policy_id=policy.id)
        policy.levels = [level]

        db.execute = AsyncMock(return_value=_scalar_result(policy))
        db.get = AsyncMock(return_value=user)

        result = await svc.resolve_for_app(app_id)
        assert len(result) == 1
        assert result[0].policy_id == policy.id

    @pytest.mark.asyncio
    async def test_multiple_levels_ordered(self):
        """Multiple levels are returned in level_number order."""
        svc, db = _make_service()
        user1 = _make_user("frank", "frank@example.com")
        user2 = _make_user("grace", "grace@example.com")
        policy = _make_policy()
        lvl1 = _make_level(level_number=1, user_id=user1.id, policy_id=policy.id)
        lvl2 = _make_level(level_number=2, user_id=user2.id, policy_id=policy.id)
        policy.levels = [lvl2, lvl1]  # intentionally unordered

        db.execute = AsyncMock(return_value=_scalar_result(policy))
        # db.get is called for each user lookup
        db.get = AsyncMock(side_effect=[user1, user2])

        result = await svc.resolve_for_app(uuid4())
        assert [c.level for c in result] == [1, 2]


# ===========================================================================
# get_current_oncall — unified query
# ===========================================================================

@pytest.mark.unit
class TestGetCurrentOncall:
    """Tests for OnCallService.get_current_oncall."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_schedules(self):
        """Returns empty list when no active schedules."""
        svc, db = _make_service()
        db.execute = AsyncMock(return_value=_scalars_result([]))

        result = await svc.get_current_oncall()
        assert result == []

    @pytest.mark.asyncio
    async def test_group_id_filters_schedules(self):
        """Passing group_id restricts results to that group's schedules."""
        svc, db = _make_service()
        group_id = uuid4()
        user = _make_user("henry")
        participant_id = uuid4()
        schedule = _make_schedule(
            participants=[{"user_id": str(participant_id), "role": "primary"}],
            effective_from=_utc_date(-1),
        )
        schedule.group_id = group_id

        # Return one schedule
        db.execute = AsyncMock(side_effect=[
            _scalars_result([schedule]),   # list schedules filtered by group_id
            _scalar_result(None),          # no override
        ])
        db.get = AsyncMock(side_effect=[schedule, user])

        result = await svc.get_current_oncall(group_id=group_id)
        assert len(result) == 1
        assert result[0].user_id == user.id

    @pytest.mark.asyncio
    async def test_app_id_delegates_to_resolve_for_app(self):
        """app_id triggers resolve_for_app path."""
        svc, db = _make_service()
        user = _make_user("ivan")
        policy = _make_policy()
        level = _make_level(level_number=1, user_id=user.id, policy_id=policy.id)
        policy.levels = [level]

        db.execute = AsyncMock(return_value=_scalar_result(policy))
        db.get = AsyncMock(return_value=user)

        result = await svc.get_current_oncall(app_id=uuid4())
        assert len(result) == 1
        assert result[0].user_id == user.id


# ===========================================================================
# escalate — escalation engine
# ===========================================================================

@pytest.mark.unit
class TestEscalate:
    """Tests for OnCallService.escalate."""

    @pytest.mark.asyncio
    async def test_escalates_to_next_level(self):
        """Unacked alert at level 1 → escalated to level 2."""
        svc, db = _make_service()
        user2 = _make_user("judy")
        policy = _make_policy()
        lvl1 = _make_level(level_number=1, user_id=uuid4(), policy_id=policy.id)
        lvl2 = _make_level(level_number=2, user_id=user2.id, policy_id=policy.id)
        policy.levels = [lvl1, lvl2]

        db.get = AsyncMock(side_effect=[policy, user2])

        with patch.object(svc, "_send_escalation_notification", new=AsyncMock()), \
             patch.object(svc, "_schedule_next_escalation", new=AsyncMock()):
            result = await svc.escalate(uuid4(), current_level=1, policy_id=policy.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_all_levels_exhausted_no_repeat(self):
        """All levels exhausted and repeat_count=0 → returns False."""
        svc, db = _make_service()
        policy = _make_policy(repeat_count=0)
        lvl1 = _make_level(level_number=1, user_id=uuid4(), policy_id=policy.id)
        policy.levels = [lvl1]

        db.get = AsyncMock(return_value=policy)

        with patch.object(svc, "_send_escalation_notification", new=AsyncMock()), \
             patch.object(svc, "_schedule_next_escalation", new=AsyncMock()):
            result = await svc.escalate(uuid4(), current_level=1, policy_id=policy.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_all_levels_exhausted_with_repeat_count(self):
        """All levels exhausted with repeat_count>0 → cycles back to level 1."""
        svc, db = _make_service()
        user = _make_user("karen")
        policy = _make_policy(repeat_count=1)
        lvl1 = _make_level(level_number=1, user_id=user.id, policy_id=policy.id)
        policy.levels = [lvl1]

        # First call: policy with repeat_count=1 and levels exhausted
        # Second call (cycle to level 0): policy now with repeat_count=0 but still level 1
        policy_cycle = _make_policy(repeat_count=0)
        policy_cycle.levels = [lvl1]

        db.get = AsyncMock(side_effect=[policy, policy_cycle, user])

        with patch.object(svc, "_send_escalation_notification", new=AsyncMock()), \
             patch.object(svc, "_schedule_next_escalation", new=AsyncMock()):
            result = await svc.escalate(uuid4(), current_level=1, policy_id=policy.id)

        # With repeat_count=1, it recurses once to level 0 → finds lvl1 → True
        assert result is True

    @pytest.mark.asyncio
    async def test_policy_not_found_returns_false(self):
        """Policy not found → returns False."""
        svc, db = _make_service()
        db.get = AsyncMock(return_value=None)

        result = await svc.escalate(uuid4(), current_level=1, policy_id=uuid4())
        assert result is False


# ===========================================================================
# Channel preference selection
# ===========================================================================

@pytest.mark.unit
class TestSelectChannelPreference:
    """Tests for OnCallService._select_channel_preference."""

    @pytest.mark.asyncio
    async def test_urgency_high_returns_slack_default(self):
        """high urgency without explicit channel returns 'slack' default."""
        svc, db = _make_service()
        level = _make_level(urgency="high", channel_id=None)
        pref = await svc._select_channel_preference(level)
        assert pref == "slack"

    @pytest.mark.asyncio
    async def test_urgency_low_returns_email_default(self):
        """low urgency without explicit channel returns 'email'."""
        svc, db = _make_service()
        level = _make_level(urgency="low", channel_id=None)
        pref = await svc._select_channel_preference(level)
        assert pref == "email"

    @pytest.mark.asyncio
    async def test_explicit_channel_overrides_urgency(self):
        """Explicit channel_id on level → channel's type returned."""
        svc, db = _make_service()
        channel = MagicMock()
        channel.channel_type = "slack"
        level = _make_level(urgency="high", channel_id=uuid4())

        db.get = AsyncMock(return_value=channel)

        pref = await svc._select_channel_preference(level)
        assert pref == "slack"

    @pytest.mark.asyncio
    async def test_explicit_channel_not_found_returns_default(self):
        """Channel not found → fallback to urgency default (slack for high)."""
        svc, db = _make_service()
        level = _make_level(urgency="high", channel_id=uuid4())

        db.get = AsyncMock(return_value=None)

        pref = await svc._select_channel_preference(level)
        assert pref == "slack"


# ===========================================================================
# notify_oncall integration (NotificationService)
# ===========================================================================

@pytest.mark.unit
class TestNotifyOncall:
    """Tests for NotificationService.notify_oncall."""

    @pytest.mark.asyncio
    async def test_returns_false_when_no_contacts(self):
        """notify_oncall returns False when no escalation contacts found."""
        from app.services.notification.service import NotificationService

        db = AsyncMock()
        svc = NotificationService(db)

        mock_oncall_svc = AsyncMock()
        mock_oncall_svc.resolve_for_app = AsyncMock(return_value=[])

        with patch("app.services.oncall_service.OnCallService", return_value=mock_oncall_svc):
            with patch("app.services.notification.service.OnCallService", new=lambda db: mock_oncall_svc, create=True):
                alert = MagicMock()
                alert.id = uuid4()
                alert.name = "HighCPU"
                alert.severity = "critical"
                # Directly test the logic: no contacts → return False
                svc2 = NotificationService(db)
                # Patch the local import
                import app.services.oncall_service as _ocs
                original_cls = _ocs.OnCallService

                class _MockOCS:
                    def __init__(self, _db):
                        pass
                    async def resolve_for_app(self, _app_id):
                        return []

                _ocs.OnCallService = _MockOCS
                try:
                    result = await svc2.notify_oncall(uuid4(), alert)
                finally:
                    _ocs.OnCallService = original_cls

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_notification_sent(self):
        """notify_oncall returns True when notification queued."""
        from app.schemas_oncall import EscalationContact, OnCallInfo
        from app.services.notification.service import NotificationService

        db = AsyncMock()
        svc = NotificationService(db)

        user_info = OnCallInfo(
            user_id=uuid4(),
            user_name="Alice",
            user_email="alice@example.com",
            role="primary",
            schedule_id=uuid4(),
            schedule_name="test-schedule",
            is_override=False,
            escalation_level=1,
            escalates_in_minutes=30,
        )
        contact = EscalationContact(
            level=1,
            user=user_info,
            channel_preference="email",
            timeout_minutes=30,
            policy_id=uuid4(),
        )

        import app.services.oncall_service as _ocs
        original_cls = _ocs.OnCallService

        class _MockOCS:
            def __init__(self, _db):
                pass
            async def resolve_for_app(self, _app_id):
                return [contact]

        _ocs.OnCallService = _MockOCS
        try:
            with patch.object(svc, "notify", new=AsyncMock(return_value=[uuid4()])):
                alert = MagicMock()
                alert.id = uuid4()
                alert.name = "DiskFull"
                alert.severity = "warning"
                result = await svc.notify_oncall(uuid4(), alert)
        finally:
            _ocs.OnCallService = original_cls

        assert result is True
