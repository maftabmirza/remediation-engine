-- Add pii_mapping_json column to ai_sessions for consistent PII redaction across conversations
-- Created: 2026-01-31

-- Add pii_mapping_json column to store PII placeholder mappings per session
-- Structure: {
--   "[EMAIL_ADDRESS_1]": "john@example.com",
--   "[EMAIL_ADDRESS_2]": "jane@company.com",
--   "_counters": {"EMAIL_ADDRESS": 2, "PHONE_NUMBER": 0, ...},
--   "_reverse": {"john@example.com": "[EMAIL_ADDRESS_1]", ...}
-- }
ALTER TABLE public.ai_sessions 
ADD COLUMN IF NOT EXISTS pii_mapping_json jsonb DEFAULT '{}'::jsonb;

-- Add comment for documentation
COMMENT ON COLUMN public.ai_sessions.pii_mapping_json IS 
'PII/Secret placeholder mappings for consistent redaction across conversation. Contains forward mapping (placeholder→original), reverse mapping (original→placeholder), and counters per entity type.';

-- Create index for sessions that have PII mappings (for auditing/reporting)
CREATE INDEX IF NOT EXISTS ix_ai_sessions_has_pii_mapping 
ON public.ai_sessions ((pii_mapping_json IS NOT NULL AND pii_mapping_json != '{}'::jsonb))
WHERE pii_mapping_json IS NOT NULL AND pii_mapping_json != '{}'::jsonb;
