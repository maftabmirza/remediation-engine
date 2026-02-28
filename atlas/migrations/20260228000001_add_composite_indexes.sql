-- Add composite indexes for frequently-queried field combinations.
-- These address N+1 query patterns and high-frequency lookups identified in code review.

-- alerts: dedup check in webhook (fingerprint + timestamp exact match)
CREATE INDEX ix_alerts_fingerprint_timestamp ON public.alerts USING btree (fingerprint, "timestamp");

-- alerts: common dashboard/listing filter (firing unanalyzed alerts)
CREATE INDEX ix_alerts_status_analyzed ON public.alerts USING btree (status, analyzed);

-- auto_analyze_rules: rules engine fetches enabled rules ordered by priority on every alert
CREATE INDEX ix_auto_analyze_rules_enabled_priority ON public.auto_analyze_rules USING btree (enabled, priority);

-- runbook_executions: similarity service resolves latest successful execution per alert
CREATE INDEX ix_runbook_executions_alert_id_status ON public.runbook_executions USING btree (alert_id, status);
