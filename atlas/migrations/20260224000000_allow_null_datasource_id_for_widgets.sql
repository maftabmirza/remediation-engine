-- Allow NULL datasource_id on prometheus_panels for static widget panels
-- Created: 2026-02-24
-- Widget panels (panel_type = 'widget') do not query any Prometheus datasource,
-- so datasource_id must be nullable to support them.

ALTER TABLE prometheus_panels ALTER COLUMN datasource_id DROP NOT NULL;
