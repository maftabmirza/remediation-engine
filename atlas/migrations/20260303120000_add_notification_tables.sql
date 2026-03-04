-- Add notification system tables: channels, policies, log

-- ============================================================================
-- notification_channels: configured delivery destinations
-- ============================================================================
CREATE TABLE public.notification_channels (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    channel_type character varying(20) NOT NULL,
    config_json jsonb NOT NULL DEFAULT '{}',
    is_enabled boolean NOT NULL DEFAULT true,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT notification_channels_pkey PRIMARY KEY (id),
    CONSTRAINT notification_channels_type_check CHECK (
        channel_type IN ('slack', 'msteams', 'email', 'webhook')
    )
);

ALTER TABLE ONLY public.notification_channels
    ADD CONSTRAINT fk_notification_channels_created_by FOREIGN KEY (created_by)
        REFERENCES public.users(id) ON DELETE SET NULL;

CREATE INDEX ix_notification_channels_channel_type ON public.notification_channels USING btree (channel_type);
CREATE INDEX ix_notification_channels_is_enabled ON public.notification_channels USING btree (is_enabled);

-- ============================================================================
-- notification_policies: rules mapping events to channels
-- ============================================================================
CREATE TABLE public.notification_policies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    event_type character varying(50) NOT NULL,
    severity_filter character varying(20)[],
    channel_ids uuid[] NOT NULL DEFAULT '{}',
    is_enabled boolean NOT NULL DEFAULT true,
    template_key character varying(50),
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT notification_policies_pkey PRIMARY KEY (id)
);

ALTER TABLE ONLY public.notification_policies
    ADD CONSTRAINT fk_notification_policies_created_by FOREIGN KEY (created_by)
        REFERENCES public.users(id) ON DELETE SET NULL;

CREATE INDEX ix_notification_policies_event_type ON public.notification_policies USING btree (event_type);
CREATE INDEX ix_notification_policies_is_enabled ON public.notification_policies USING btree (is_enabled);

-- ============================================================================
-- notification_log: delivery audit trail
-- ============================================================================
CREATE TABLE public.notification_log (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    policy_id uuid,
    channel_id uuid NOT NULL,
    event_type character varying(50) NOT NULL,
    event_id uuid,
    recipient character varying(255),
    status character varying(20) NOT NULL DEFAULT 'pending',
    attempt_count integer NOT NULL DEFAULT 0,
    error_message text,
    payload_json jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    sent_at timestamp with time zone,
    next_retry_at timestamp with time zone,
    CONSTRAINT notification_log_pkey PRIMARY KEY (id),
    CONSTRAINT notification_log_status_check CHECK (
        status IN ('pending', 'sent', 'failed', 'retrying')
    )
);

ALTER TABLE ONLY public.notification_log
    ADD CONSTRAINT fk_notification_log_policy FOREIGN KEY (policy_id)
        REFERENCES public.notification_policies(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.notification_log
    ADD CONSTRAINT fk_notification_log_channel FOREIGN KEY (channel_id)
        REFERENCES public.notification_channels(id) ON DELETE CASCADE;

CREATE INDEX idx_notification_log_status ON public.notification_log USING btree (status);
CREATE INDEX idx_notification_log_event ON public.notification_log USING btree (event_type, event_id);
CREATE INDEX idx_notification_log_created ON public.notification_log USING btree (created_at);
CREATE INDEX idx_notification_log_next_retry ON public.notification_log USING btree (next_retry_at) WHERE status = 'retrying';
