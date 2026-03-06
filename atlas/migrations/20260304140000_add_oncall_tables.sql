-- On-Call Scheduling & Escalation tables (Feature A1)

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
    CONSTRAINT oncall_schedules_rotation_type_check CHECK (rotation_type IN ('daily', 'weekly', 'custom')),
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
    CONSTRAINT escalation_levels_urgency_check CHECK (urgency IN ('high', 'low')),
    CONSTRAINT escalation_levels_target_check CHECK (
        (schedule_id IS NOT NULL AND user_id IS NULL) OR
        (schedule_id IS NULL AND user_id IS NOT NULL)
    ),
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
