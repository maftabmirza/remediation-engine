-- Add SSO / CyberArk Identity fields to users table
-- These columns are nullable; existing local users are unaffected.
-- sso_subject   : CyberArk SAML NameID (unique per SSO user, sparse index)
-- auth_provider : "local" (default) or "cyberark"

ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "sso_subject" character varying(255);
ALTER TABLE "users" ADD COLUMN IF NOT EXISTS "auth_provider" character varying(50) DEFAULT 'local';

CREATE UNIQUE INDEX IF NOT EXISTS "uq_users_sso_subject"
    ON "users" ("sso_subject")
    WHERE "sso_subject" IS NOT NULL;

CREATE INDEX IF NOT EXISTS "ix_users_auth_provider"
    ON "users" ("auth_provider");
