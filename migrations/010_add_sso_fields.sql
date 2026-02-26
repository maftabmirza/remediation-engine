-- Migration 010: Add SSO / CyberArk Identity fields to users table
-- These columns are nullable; existing local users are unaffected.
-- sso_subject   : CyberArk NameID (unique per SSO user)
-- auth_provider : "local" (default) or "cyberark"

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS sso_subject   VARCHAR(255) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(50)  DEFAULT 'local';

-- Unique index on sso_subject (sparse: NULL values are excluded from uniqueness)
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_sso_subject
    ON users (sso_subject)
    WHERE sso_subject IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_users_auth_provider
    ON users (auth_provider);
