-- Add multi-server and server-group support to scheduled_jobs
ALTER TABLE public.scheduled_jobs ADD COLUMN IF NOT EXISTS target_server_ids jsonb DEFAULT '[]'::jsonb;
ALTER TABLE public.scheduled_jobs ADD COLUMN IF NOT EXISTS target_server_group_ids jsonb DEFAULT '[]'::jsonb;
