-- Post-Incident Postmortem Reports Table
-- Phase 2: Post-Incident Review / Postmortem Generation (A4)

CREATE TABLE public.postmortem_reports (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title character varying(500) NOT NULL,
    alert_id uuid,
    app_id uuid,
    status character varying(20) DEFAULT 'draft' NOT NULL,
    incident_start timestamp with time zone,
    incident_end timestamp with time zone,
    severity character varying(20),
    timeline jsonb DEFAULT '[]'::jsonb,
    impact_summary text,
    root_cause text,
    contributing_factors jsonb DEFAULT '[]'::jsonb,
    remediation_actions jsonb DEFAULT '[]'::jsonb,
    action_items jsonb DEFAULT '[]'::jsonb,
    lessons_learned text,
    metrics jsonb DEFAULT '{}'::jsonb,
    generated_by character varying(20) DEFAULT 'ai',
    out_of_band_context jsonb DEFAULT '[]'::jsonb,
    reviewed_by uuid,
    created_by uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT postmortem_reports_pkey PRIMARY KEY (id),
    CONSTRAINT postmortem_reports_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alerts(id) ON DELETE SET NULL,
    CONSTRAINT postmortem_reports_app_id_fkey FOREIGN KEY (app_id) REFERENCES public.applications(id) ON DELETE SET NULL,
    CONSTRAINT postmortem_reports_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(id) ON DELETE SET NULL,
    CONSTRAINT postmortem_reports_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL
);

CREATE INDEX ix_postmortem_reports_alert_id ON public.postmortem_reports USING btree (alert_id);
CREATE INDEX ix_postmortem_reports_app_id ON public.postmortem_reports USING btree (app_id);
CREATE INDEX ix_postmortem_reports_status ON public.postmortem_reports USING btree (status);
CREATE INDEX ix_postmortem_reports_created_at ON public.postmortem_reports USING btree (created_at);
