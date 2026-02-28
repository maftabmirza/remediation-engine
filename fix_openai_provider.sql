-- Fix the specific provider that has wrong type
UPDATE llm_providers 
SET provider_type = 'openai'
WHERE name = 'OpenAI GPT-4' 
  AND model_id LIKE 'gpt%';

-- Verify the fix
SELECT id, name, provider_type, model_id, is_enabled 
FROM llm_providers 
ORDER BY created_at;
