-- Add usage_type to llm_providers
-- 'llm' = general language model (default), 'embedding' = vector embedding model
ALTER TABLE public.llm_providers ADD COLUMN usage_type character varying(20) NOT NULL DEFAULT 'llm';

-- Index for filtering by usage_type
CREATE INDEX ix_llm_providers_usage_type ON public.llm_providers USING btree (usage_type);
