-- Add password policy enforcement columns to users table
-- failed_login_attempts: tracks consecutive failed logins for account lockout
-- locked_until: timestamp until which the account is locked (NULL = not locked)
-- password_changed_at: timestamp of last password change (for expiry enforcement)

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS failed_login_attempts integer NOT NULL DEFAULT 0;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS locked_until timestamp with time zone;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS password_changed_at timestamp with time zone;

CREATE INDEX IF NOT EXISTS ix_users_locked_until ON public.users USING btree (locked_until);
