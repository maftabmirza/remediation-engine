# Implementation Plan — Phase 4 of 4
# Feature: On-Call Scheduling & Escalation — Native Notification Extension (A1)

## HOW TO USE THIS PHASE
Ensure Phases 1, 2, and 3 are complete first.
This is the final and most complex feature. After this, the full implementation is done.

---

## Reminder: Project Standards
- PEP 8, type hints on ALL arguments/returns, async-first for I/O
- `@pytest.mark.unit` + `@pytest.mark.asyncio` for tests
- `Depends(get_current_user)` read / `Depends(require_admin)` or `require_role([...])` write
- Atlas migrations: NEVER raw DDL — always migration file + `atlas migrate hash` + `atlas migrate apply`
- Min 3 tests per function: happy path, error, edge case
- CSS: CSS variables only, `.modal-overlay` for modals, `window.showToast()` for notifications

### Key Files Already in Project (extend, don't replace)
| Purpose | File |
|---------|------|
| Existing notification dispatcher | app/services/notification/dispatcher.py |
| Existing notification service | app/services/notification/service.py |
| Group/GroupMember models (teams) | app/models.py |
| User model (email, phone) | app/models.py |
| NotificationChannel model | app/models.py |
| APScheduler infrastructure | app/services/scheduler_service.py |
| MCP adapter stubs | app/services/agentic/tools/mcp_adapters.py |
| Context enricher | app/services/agentic/context_enricher.py |

---

## Feature 7: On-Call Scheduling & Escalation (A1) — P1

### Goal
Extend the existing `NotificationChannel` → `NotificationPolicy` → `NotificationDispatcher` architecture with on-call rotations and escalation policies. Alerts route to the right person at the right time. Built natively because Grafana OnCall is being sunset.

**Design philosophy:** This is NOT a separate system. It's an extension of existing notification infrastructure. On-call schedules link to `Group` (teams). Escalation levels reference `NotificationChannel` (delivery methods). The dispatcher resolves on-call before sending.

### Files to Create
- `app/models_oncall.py` — OnCallSchedule, EscalationPolicy, EscalationLevel, OnCallOverride
- `app/schemas_oncall.py` — Pydantic schemas
- `app/services/oncall_service.py` — Rotation resolution + escalation engine
- `app/routers/oncall_api.py` — CRUD + "who is on-call?" endpoints
- `atlas/migrations/20260304140000_add_oncall_tables.sql` — Migration
- `tests/unit/services/test_oncall_service.py` — Tests

### Files to Modify
- `schema/schema.sql` — Add 4 new tables
- `app/services/notification/dispatcher.py` — Resolve on-call before sending alert notifications
- `app/services/notification/service.py` — Add `notify_oncall()` method
- `app/services/agentic/tools/mcp_adapters.py` — Complete `OnCallAdapter` stub with real service calls
- `app/services/agentic/context_enricher.py` — Add real on-call data to enriched context
- `app/main.py` — Register new router

---

## Models (app/models_oncall.py)

### OnCallSchedule
```
id:               UUID, PK, default gen_random_uuid()
name:             VARCHAR(100), NOT NULL
group_id:         UUID, FK groups (team whose members rotate)
rotation_type:    VARCHAR(20), NOT NULL  -- "daily", "weekly", "custom"
participants:     JSONB, NOT NULL  -- [{"user_id": "uuid", "order": 1}, ...]
                  -- Ordered list; subset of group members
timezone:         VARCHAR(50), NOT NULL  -- "America/New_York"
handoff_time:     TIME, NOT NULL  -- "09:00" (when rotation shifts each day)
handoff_day:      VARCHAR(10)  -- "monday" (for weekly rotation only, nullable)
effective_from:   TIMESTAMPTZ, NOT NULL
effective_until:  TIMESTAMPTZ (nullable -- NULL = indefinite)
is_active:        BOOLEAN DEFAULT TRUE
created_by:       UUID, FK users
created_at:       TIMESTAMPTZ DEFAULT now()
updated_at:       TIMESTAMPTZ DEFAULT now()
```

**Rotation layers**: `participants` JSON supports primary/secondary/shadow roles:
```json
[
  {"user_id": "uuid-1", "order": 1, "role": "primary"},
  {"user_id": "uuid-2", "order": 2, "role": "secondary"},
  {"user_id": "uuid-3", "order": 3, "role": "shadow"}
]
```

### EscalationPolicy
```
id:               UUID, PK, default gen_random_uuid()
name:             VARCHAR(100), NOT NULL
app_id:           UUID, FK applications (nullable -- service-specific; NULL = default)
description:      TEXT
repeat_count:     INTEGER DEFAULT 0  -- How many times to cycle through all levels before giving up
resolve_timeout_minutes: INTEGER DEFAULT 60  -- Re-escalate if ack'd but not resolved after this time
is_default:       BOOLEAN DEFAULT FALSE  -- Fallback when no app-specific policy exists
is_active:        BOOLEAN DEFAULT TRUE
created_by:       UUID, FK users
created_at:       TIMESTAMPTZ DEFAULT now()
updated_at:       TIMESTAMPTZ DEFAULT now()
```

### EscalationLevel
```
id:               UUID, PK, default gen_random_uuid()
policy_id:        UUID, FK escalation_policies, ON DELETE CASCADE
level_number:     INTEGER, NOT NULL  -- 1, 2, 3...
schedule_id:      UUID, FK oncall_schedules (nullable -- notify whoever is on-call)
user_id:          UUID, FK users (nullable -- OR notify specific user)
channel_id:       UUID, FK notification_channels (nullable -- override delivery channel)
timeout_minutes:  INTEGER DEFAULT 30  -- Escalate to next level if not ack'd within this time
urgency:          VARCHAR(20) DEFAULT 'high'  -- "high" or "low" (affects channel selection)
notification_steps: JSONB DEFAULT '[]'  -- [{channel_id, delay_minutes}] ordered steps within level
created_at:       TIMESTAMPTZ DEFAULT now()
```

Note: When `urgency = 'high'`: prefer SMS/Phone channels. When `urgency = 'low'`: prefer Slack/Email. The `channel_id` on the level overrides this preference. `notification_steps` allows sending to Slack first, then SMS after 5 min if no ack.

Constraint: Either `schedule_id` OR `user_id` must be set (not both, not neither).

### OnCallOverride
```
id:               UUID, PK, default gen_random_uuid()
schedule_id:      UUID, FK oncall_schedules, ON DELETE CASCADE
override_user_id: UUID, FK users (who is covering)
starts_at:        TIMESTAMPTZ, NOT NULL
ends_at:          TIMESTAMPTZ, NOT NULL
reason:           VARCHAR(500)
created_by:       UUID, FK users
created_at:       TIMESTAMPTZ DEFAULT now()
```

---

## Migration SQL (20260304140000_add_oncall_tables.sql)
```sql
CREATE TABLE public.oncall_schedules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    group_id uuid NOT NULL,
    rotation_type character varying(20) NOT NULL,
    participants jsonb NOT NULL DEFAULT '[]'::jsonb,
    timezone character varying(50) NOT NULL DEFAULT 'UTC',
    handoff_time time without time zone NOT NULL DEFAULT '09:00',
    handoff_day character varying(10),
    effective_from timestamp with time zone NOT NULL,
    effective_until timestamp with time zone,
    is_active boolean DEFAULT true NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT oncall_schedules_pkey PRIMARY KEY (id),
    CONSTRAINT oncall_schedules_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id),
    CONSTRAINT oncall_schedules_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id)
);

CREATE TABLE public.escalation_policies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    app_id uuid,
    description text,
    repeat_count integer DEFAULT 0,
    resolve_timeout_minutes integer DEFAULT 60,
    is_default boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT escalation_policies_pkey PRIMARY KEY (id),
    CONSTRAINT escalation_policies_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.applications(id),
    CONSTRAINT escalation_policies_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id)
);

CREATE TABLE public.escalation_levels (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    policy_id uuid NOT NULL,
    level_number integer NOT NULL,
    schedule_id uuid,
    user_id uuid,
    channel_id uuid,
    timeout_minutes integer DEFAULT 30,
    urgency character varying(20) DEFAULT 'high',
    notification_steps jsonb DEFAULT '[]'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT escalation_levels_pkey PRIMARY KEY (id),
    CONSTRAINT escalation_levels_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.escalation_policies(id) ON DELETE CASCADE,
    CONSTRAINT escalation_levels_schedule_id_fkey FOREIGN KEY (schedule_id) REFERENCES public.oncall_schedules(id),
    CONSTRAINT escalation_levels_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id),
    CONSTRAINT escalation_levels_channel_id_fkey FOREIGN KEY (channel_id) REFERENCES public.notification_channels(id)
);

CREATE TABLE public.oncall_overrides (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    schedule_id uuid NOT NULL,
    override_user_id uuid NOT NULL,
    starts_at timestamp with time zone NOT NULL,
    ends_at timestamp with time zone NOT NULL,
    reason character varying(500),
    created_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT oncall_overrides_pkey PRIMARY KEY (id),
    CONSTRAINT oncall_overrides_schedule_id_fkey FOREIGN KEY (schedule_id) REFERENCES public.oncall_schedules(id) ON DELETE CASCADE,
    CONSTRAINT oncall_overrides_user_id_fkey FOREIGN KEY (override_user_id) REFERENCES public.users(id),
    CONSTRAINT oncall_overrides_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id)
);

CREATE INDEX ix_oncall_schedules_group_id ON public.oncall_schedules USING btree (group_id);
CREATE INDEX ix_oncall_schedules_is_active ON public.oncall_schedules USING btree (is_active);
CREATE INDEX ix_escalation_policies_app_id ON public.escalation_policies USING btree (app_id);
CREATE INDEX ix_escalation_policies_is_default ON public.escalation_policies USING btree (is_default);
CREATE INDEX ix_escalation_levels_policy_id ON public.escalation_levels USING btree (policy_id);
CREATE INDEX ix_oncall_overrides_schedule_id ON public.oncall_overrides USING btree (schedule_id);
```

---

## Schemas (app/schemas_oncall.py)

### Input schemas
- `OnCallScheduleCreate`: all required fields, `participants: List[dict]`
- `OnCallScheduleUpdate`: all optional
- `EscalationPolicyCreate`: name, app_id (optional), description, repeat_count, resolve_timeout_minutes
- `EscalationLevelCreate`: policy_id, level_number, schedule_id OR user_id (validated), channel_id, timeout_minutes, urgency, notification_steps
- `OnCallOverrideCreate`: schedule_id, override_user_id, starts_at, ends_at, reason

### Output schemas
- `OnCallInfo`:
  ```python
  class OnCallInfo(BaseModel):
      user_id: UUID
      user_name: str
      user_email: str
      role: str               # "primary", "secondary", "shadow"
      schedule_id: UUID
      schedule_name: str
      is_override: bool
      escalation_level: int   # 1 = first responder
      escalates_in_minutes: Optional[int]  # Time until next escalation level
  ```
- `EscalationContact`: `{level: int, user: OnCallInfo, channel_preference: str, timeout_minutes: int}`
- `OnCallScheduleResponse`, `EscalationPolicyResponse`, `EscalationLevelResponse`, `OnCallOverrideResponse`
- `OnCallTimelineEntry`: `{starts_at, ends_at, user_id, user_name, is_override}`
- List response types with pagination

---

## Service: OnCallService (app/services/oncall_service.py)

### `resolve_current_oncall(schedule_id: UUID, at_time: Optional[datetime] = None, db: AsyncSession) -> Optional[OnCallInfo]`

Algorithm:
1. `at_time` defaults to `datetime.now(UTC)`
2. Check active overrides: query `OnCallOverride` where `schedule_id = schedule_id AND starts_at <= at_time AND ends_at >= at_time`. Return override user if found (highest priority).
3. Load schedule. Convert `at_time` to schedule's `timezone` using `pytz` or `zoneinfo`.
4. Calculate rotation position:
   - For `rotation_type = "daily"`: `days_elapsed = (at_time.date() - effective_from.date()).days`; `participant_index = days_elapsed % len(participants)`
   - For `rotation_type = "weekly"`: `weeks_elapsed = days_elapsed // 7`; `participant_index = weeks_elapsed % len(participants)`
   - Respect `handoff_time`: if current time < `handoff_time`, use previous day's assignment
   - DST handling: always use timezone-aware datetime, never naive datetime
5. Return `OnCallInfo` for the participant at computed index across all roles (primary, secondary, shadow)

### `resolve_for_app(app_id: UUID, db: AsyncSession) -> List[EscalationContact]`

1. Find `EscalationPolicy` where `app_id = app_id AND is_active = True` (first match)
2. Fall back to `EscalationPolicy` where `is_default = True AND is_active = True`
3. If no policy found: return empty list
4. For each `EscalationLevel` (ordered by `level_number`):
   - If `schedule_id` set: call `resolve_current_oncall(schedule_id)`
   - If `user_id` set: load that user directly
   - Select channel: use level's `channel_id` if set, else select by `urgency` (high → SMS/Phone, low → Slack/Email) from available `NotificationChannel` records
5. Return ordered `EscalationContact` list

### `escalate(alert_id: UUID, current_level: int, policy_id: UUID, db: AsyncSession) -> bool`

Called by APScheduler when ack timeout expires for a level:
1. Load `EscalationPolicy` and its levels ordered by `level_number`
2. Find next level > `current_level`
3. If next level exists:
   - Resolve on-call for that level
   - Call `NotificationService.send_immediate(user, alert, channel)` 
   - Update alert's escalation tracking (store `current_escalation_level` on alert or in a separate `EscalationState` table)
   - Schedule next escalation timeout via `APScheduler`
   - Return `True`
4. If no next level:
   - Check `repeat_count > 0` → cycle back to level 1, decrement repeat count
   - If truly exhausted: log warning, notify all levels as bulk fallback, return `False`

### `get_current_oncall(group_id: Optional[UUID], app_id: Optional[UUID], db: AsyncSession) -> List[OnCallInfo]`

"Who is on-call right now?" for UI, API, and AI agents:
1. If `app_id`: call `resolve_for_app(app_id)`, return all escalation contacts with their on-call resolution
2. If `group_id`: find all active schedules for the group, call `resolve_current_oncall()` for each
3. If neither: return all active schedules' current on-call across all groups

### Escalation State Tracking
Add a lightweight `escalation_state` JSONB column to `Alert` (in a separate small migration) or use a Redis-backed APScheduler job state. Store: `{policy_id, current_level, acked_at, escalation_scheduled_job_id}`. This allows the dispatcher and escalate() to know current state.

OR: Create a simple in-memory-safe approach — store escalation job ID in `Alert.metadata` JSON field if it already exists, to avoid another migration.

---

## Notification Dispatcher Integration

In `app/services/notification/dispatcher.py`, extend the alert firing handler:

```python
# When routing a firing alert:
async def route_alert(alert: Alert, db: AsyncSession) -> None:
    # ... existing routing logic ...

    # NEW: Check if alert's app has an escalation policy
    if alert.app_id:
        escalation_contacts = await oncall_service.resolve_for_app(alert.app_id, db)
        if escalation_contacts:
            level_1 = escalation_contacts[0]
            # Send to level 1 on-call via their preferred channel
            await notification_service.send_immediate(
                user=level_1.user,
                alert=alert,
                channel=level_1.channel_preference
            )
            # Schedule escalation timeout via APScheduler
            await scheduler_service.schedule_escalation(
                alert_id=alert.id,
                policy_id=level_1.policy_id,
                current_level=1,
                delay_minutes=level_1.timeout_minutes
            )
            return  # Skip standard channel routing if policy exists

    # ... existing channel routing for alerts without policy ...
```

In `app/services/notification/service.py`, add:
```python
async def notify_oncall(app_id: UUID, alert: Alert, db: AsyncSession) -> bool:
    """Resolve on-call and send immediate notification. Returns True if sent."""
```

---

## MCP Adapter Completion

In `app/services/agentic/tools/mcp_adapters.py`, find the `OnCallAdapter` stub and replace with real calls:

```python
class OnCallAdapter:
    def __init__(self, oncall_service: OnCallService):
        self.oncall_service = oncall_service

    async def get_current_oncall(self, app_id: Optional[str] = None, group_id: Optional[str] = None) -> dict:
        """Tool callable by AI agents: 'Who is on-call for this service?'"""
        result = await self.oncall_service.get_current_oncall(
            group_id=UUID(group_id) if group_id else None,
            app_id=UUID(app_id) if app_id else None,
            db=self.db
        )
        return {
            "oncall": [
                {
                    "name": c.user_name,
                    "email": c.user_email,
                    "role": c.role,
                    "level": c.escalation_level,
                    "escalates_in_minutes": c.escalates_in_minutes
                }
                for c in result
            ]
        }
```

In `app/services/agentic/context_enricher.py`, update on-call enrichment:
- Call `OnCallAdapter.get_current_oncall(app_id=alert.app_id)`
- Add to context: `"On-call: @{name} (Level {level}, escalates in {n}min if no acknowledgement)"`

---

## Router: /api/oncall/ (app/routers/oncall_api.py)

### Schedule Management
- `GET /api/oncall/schedules` — List (paginated, filter by group_id), auth: `get_current_user`
- `POST /api/oncall/schedules` — Create, auth: `require_admin`
- `GET /api/oncall/schedules/{id}` — Get, auth: `get_current_user`
- `PUT /api/oncall/schedules/{id}` — Update, auth: `require_admin`
- `DELETE /api/oncall/schedules/{id}` — Deactivate, auth: `require_admin`
- `GET /api/oncall/schedules/{id}/timeline` — Upcoming rotation view (next 30 days), auth: `get_current_user`

### Escalation Policy Management
- `GET /api/oncall/escalation-policies` — List, auth: `get_current_user`
- `POST /api/oncall/escalation-policies` — Create, auth: `require_admin`
- `GET /api/oncall/escalation-policies/{id}` — Get with levels, auth: `get_current_user`
- `PUT /api/oncall/escalation-policies/{id}` — Update, auth: `require_admin`
- `DELETE /api/oncall/escalation-policies/{id}` — Deactivate, auth: `require_admin`
- `POST /api/oncall/escalation-policies/{id}/levels` — Add level, auth: `require_admin`
- `DELETE /api/oncall/escalation-policies/{id}/levels/{level_id}` — Remove level, auth: `require_admin`

### Override Management
- `POST /api/oncall/overrides` — Create override (swap), auth: `get_current_user` (own) / `require_admin` (others)
- `DELETE /api/oncall/overrides/{id}` — Cancel override, auth: `get_current_user`

### Current On-Call Queries
- `GET /api/oncall/current` — Who is on-call right now (query params: `app_id`, `group_id`), auth: `get_current_user`
- `GET /api/oncall/current/app/{app_id}` — Full escalation chain for an app, auth: `get_current_user`

---

## Tests (test_oncall_service.py)

### Rotation Tests
- Daily rotation day 0: first participant returned
- Daily rotation day N: correct participant returned using modulo
- Weekly rotation: correct week offset calculated
- Handoff time respected: at 08:59 → previous day's person; at 09:01 → new person
- DST transition: schedule crosses daylight saving time boundary — no skipped or doubled shifts
- Override priority: active override returns override_user, not rotation user
- Override not yet active: `starts_at` in future → rotation user returned
- Override expired: `ends_at` in past → rotation user returned
- Empty schedule: no participants → returns None

### Escalation Tests
- Level 1 escalation: unack'd alert after timeout → level 2 user notified
- Level 2 escalation: after second timeout → level 3 user notified
- All levels exhausted, repeat_count = 0: returns False, warning logged
- All levels exhausted, repeat_count = 2: cycles to level 1 twice, then exhausted
- `resolve_timeout`: ack'd but not resolved after resolve_timeout → re-escalation triggered
- No policy for app: falls back to `is_default = True` policy
- No default policy: returns empty list
- `get_current_oncall(app_id=...)`: returns ordered escalation chain with correct users

### Notification Step Tests
- `urgency = 'high'`: SMS/Phone channel selected when multiple available
- `urgency = 'low'`: Slack/Email channel selected
- `notification_steps` override: specific steps sent in order with delays

---

## Deliverables for Phase 4 (Final)
After implementing this feature, verify:
- [ ] `pytest tests/unit/services/test_oncall_service.py -v` passes (all rotation, escalation, and notification tests)
- [ ] Atlas migration `20260304140000_add_oncall_tables.sql` applied successfully
- [ ] `schema/schema.sql` updated with all 4 new tables
- [ ] `OnCallAdapter` stub in `mcp_adapters.py` replaced with real implementation
- [ ] `context_enricher.py` shows real on-call data
- [ ] `dispatcher.py` resolves on-call before routing
- [ ] On-call router registered in `app/main.py`
- [ ] APScheduler escalation timeout jobs scheduled correctly
- [ ] `docker compose up -d --build remediation-engine` succeeds

---

## Complete Implementation Summary

All 7 features are now implemented:

| # | Feature | Priority | Status |
|---|---------|----------|--------|
| F1 | RAG-Enhanced Alert Diagnosis (B7) | P0 | Phase 1 |
| F2 | Alert Suppression Rules (A6) | P0 | Phase 1 |
| F3 | Remediation Confidence Score (B6) | P0 | Phase 2 |
| F4 | Postmortem Generation (A4) | P1 | Phase 2 |
| F5 | Runbook Auto-Generation (B2) | P1 | Phase 3 |
| F6 | Service Health Score & Topology (A2) | P1 | Phase 3 |
| F7 | On-Call & Escalation (A1) | P1 | Phase 4 |

### Final Verification Commands
```bash
# Run all unit tests
pytest tests/unit -v

# Run integration tests (requires DB)
pytest tests/integration -v

# Check Atlas migration status
docker compose exec remediation-engine atlas migrate status \
  --dir "file:///app/atlas/migrations" \
  --url "$DATABASE_URL"

# Tail logs to verify no startup errors
docker logs -f remediation-engine
```
