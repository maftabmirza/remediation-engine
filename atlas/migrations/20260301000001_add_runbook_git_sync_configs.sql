-- Add runbook_git_sync_configs table for Git-based runbook synchronisation
CREATE TABLE public.runbook_git_sync_configs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(100) NOT NULL,
    repo_url character varying(500) NOT NULL,
    branch character varying(100) NOT NULL DEFAULT 'main',
    path_prefix character varying(255),
    auth_type character varying(20) NOT NULL DEFAULT 'none',
    token_encrypted text,
    username character varying(255),
    password_encrypted text,
    ssh_key_encrypted text,
    enabled boolean NOT NULL DEFAULT true,
    sync_interval_minutes integer NOT NULL DEFAULT 60,
    overwrite_existing boolean NOT NULL DEFAULT true,
    last_sync_at timestamp with time zone,
    last_sync_status character varying(20) NOT NULL DEFAULT 'never',
    last_sync_message text,
    runbooks_synced integer NOT NULL DEFAULT 0,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT runbook_git_sync_configs_pkey PRIMARY KEY (id),
    CONSTRAINT runbook_git_sync_configs_auth_type_check CHECK (
        auth_type IN ('none', 'token', 'ssh', 'basic')
    ),
    CONSTRAINT runbook_git_sync_configs_status_check CHECK (
        last_sync_status IN ('never', 'pending', 'running', 'success', 'error')
    ),
    CONSTRAINT fk_runbook_git_sync_created_by FOREIGN KEY (created_by)
        REFERENCES public.users(id) ON DELETE SET NULL
);

CREATE INDEX ix_runbook_git_sync_configs_enabled ON public.runbook_git_sync_configs USING btree (enabled);
CREATE INDEX ix_runbook_git_sync_configs_last_sync_at ON public.runbook_git_sync_configs USING btree (last_sync_at);
