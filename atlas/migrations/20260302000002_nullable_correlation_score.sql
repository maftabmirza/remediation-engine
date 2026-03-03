-- Make correlation_score nullable since the AlertCorrelation model uses confidence_score
-- instead. The old column exists from the original link-table design and is no longer
-- populated by the CorrelationService.
ALTER TABLE public.alert_correlations
    ALTER COLUMN correlation_score DROP NOT NULL;
