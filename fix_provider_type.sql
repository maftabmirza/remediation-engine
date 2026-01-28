-- Fix provider_type case sensitivity
-- Run this inside the postgres container

UPDATE llm_providers 
SET provider_type = LOWER(TRIM(provider_type))
WHERE provider_type != LOWER(TRIM(provider_type));

-- Verify the fix
SELECT id, name, provider_type, model_id, is_enabled 
FROM llm_providers 
ORDER BY created_at;
