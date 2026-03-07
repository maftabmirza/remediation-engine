-- Incident-First Postmortems
-- Adds the native Incident aggregate table and links it to postmortem_reports.
--
-- Step 1: Create the incidents table (native incident aggregate).
-- Step 2: Add incident_id FK to postmortem_reports.

-- ─── 1. incidents table ────────────────────────────────────────────────────

CREATE TABLE public.incidents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    title character varying(500) NOT NULL,
    status character varying(50) DEFAULT 'open' NOT NULL,
    severity character varying(20),
    correlation_id uuid,
    cluster_id uuid,
    itsm_event_id uuid,
    started_at timestamp with time zone NOT NULL,
    resolved_at timestamp with time zone,
    grace_period_ends_at timestamp with time zone,
    is_eligible_for_postmortem boolean DEFAULT false NOT NULL,
    affected_services jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT incidents_pkey PRIMARY KEY (id),
    CONSTRAINT incidents_correlation_id_fkey FOREIGN KEY (correlation_id)
        REFERENCES public.alert_correlations(id) ON DELETE SET NULL,
    CONSTRAINT incidents_cluster_id_fkey FOREIGN KEY (cluster_id)
        REFERENCES public.alert_clusters(id) ON DELETE SET NULL,
    CONSTRAINT incidents_itsm_event_id_fkey FOREIGN KEY (itsm_event_id)
        REFERENCES public.incident_events(id) ON DELETE SET NULL
);

CREATE INDEX ix_incidents_status           ON public.incidents USING btree (status);
CREATE INDEX ix_incidents_severity         ON public.incidents USING btree (severity);
CREATE INDEX ix_incidents_correlation_id   ON public.incidents USING btree (correlation_id);
CREATE INDEX ix_incidents_cluster_id       ON public.incidents USING btree (cluster_id);
CREATE INDEX ix_incidents_resolved_at      ON public.incidents USING btree (resolved_at);
CREATE INDEX ix_incidents_eligible         ON public.incidents USING btree (is_eligible_for_postmortem);
CREATE INDEX ix_incidents_started_at       ON public.incidents USING btree (started_at);

-- ─── 2. Add incident_id to postmortem_reports ───────────────────────────────

ALTER TABLE public.postmortem_reports
    ADD COLUMN incident_id uuid,
    ADD CONSTRAINT postmortem_reports_incident_id_fkey
        FOREIGN KEY (incident_id) REFERENCES public.incidents(id) ON DELETE SET NULL;

CREATE INDEX ix_postmortem_reports_incident_id
    ON public.postmortem_reports USING btree (incident_id);
