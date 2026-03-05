-- ============================================================================
-- Alert Suppression Rules (Feature A6)
-- Migration: 20260305000000_add_alert_suppression_rules
-- ============================================================================

CREATE TABLE public.alert_suppression_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    alert_name_pattern character varying(255) NOT NULL DEFAULT '*',
    severity_pattern character varying(50) NOT NULL DEFAULT '*',
    instance_pattern character varying(255) NOT NULL DEFAULT '*',
    job_pattern character varying(255) NOT NULL DEFAULT '*',
    starts_at timestamp with time zone,
    ends_at timestamp with time zone,
    is_active boolean NOT NULL DEFAULT true,
    reason character varying(500),
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT alert_suppression_rules_pkey PRIMARY KEY (id)
);

ALTER TABLE ONLY public.alert_suppression_rules
    ADD CONSTRAINT fk_alert_suppression_rules_created_by FOREIGN KEY (created_by)
        REFERENCES public.users(id) ON DELETE SET NULL;

CREATE INDEX ix_alert_suppression_rules_is_active ON public.alert_suppression_rules USING btree (is_active);
