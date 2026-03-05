-- Add alert_suppression_rules table and maintenance_mode column to applications
-- Migration: 20260304120000_add_alert_suppression.sql

CREATE TABLE public.alert_suppression_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(200) NOT NULL,
    rule_type character varying(20) NOT NULL,
    matchers jsonb,
    app_id uuid,
    starts_at timestamp with time zone NOT NULL,
    ends_at timestamp with time zone,
    grace_period_minutes integer DEFAULT 5 NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT alert_suppression_rules_pkey PRIMARY KEY (id),
    CONSTRAINT alert_suppression_rules_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.applications(id) ON DELETE CASCADE,
    CONSTRAINT alert_suppression_rules_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL
);

CREATE INDEX ix_alert_suppression_rules_app_id ON public.alert_suppression_rules USING btree (app_id);
CREATE INDEX ix_alert_suppression_rules_is_active ON public.alert_suppression_rules USING btree (is_active);

ALTER TABLE public.applications ADD COLUMN IF NOT EXISTS maintenance_mode boolean DEFAULT false;
