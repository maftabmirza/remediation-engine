-- Fix alert_correlations table to match AlertCorrelation SQLAlchemy model.
-- The table was originally created with a different structure (link-table style).
-- This migration adds the missing columns and relaxes NOT NULL constraints that
-- prevent the CorrelationService from inserting new correlation rows.

-- Add missing columns expected by the AlertCorrelation model
ALTER TABLE public.alert_correlations
    ADD COLUMN IF NOT EXISTS root_cause_analysis text NULL;

ALTER TABLE public.alert_correlations
    ADD COLUMN IF NOT EXISTS confidence_score double precision NULL;

-- related_alert_id is no longer always populated (correlations now exist independently)
ALTER TABLE public.alert_correlations
    ALTER COLUMN related_alert_id DROP NOT NULL;

-- correlation_type can default to 'automatic' so inserts without it succeed
ALTER TABLE public.alert_correlations
    ALTER COLUMN correlation_type SET DEFAULT 'automatic';

ALTER TABLE public.alert_correlations
    ALTER COLUMN correlation_type DROP NOT NULL;

-- correlation_score rename/alias: add index on confidence_score for fast lookup
CREATE INDEX IF NOT EXISTS ix_alert_correlations_confidence_score
    ON public.alert_correlations USING btree (confidence_score);
