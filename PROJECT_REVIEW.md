# Project Review

## Highlights
- Clear modular architecture with FastAPI routers, services, and templates documented in the README, which will help newcomers navigate the codebase quickly.【F:README.md†L5-L81】
- Built-in rate limiting on authentication endpoints reduces the blast radius of credential-stuffing attempts.【F:app/routers/auth.py†L24-L81】
- Startup lifecycle wires in background execution workers and router registration in one place, keeping operational concerns centralized.【F:app/main.py†L88-L158】

## Risks and Gaps
- Default secrets and credentials (JWT secret, encryption key, admin username/password) ship in code and are used during startup to auto-provision an admin account, which is unsafe for any non-local deployment.【F:app/config.py†L8-L47】【F:app/main.py†L55-L85】
- Login sets a long-lived HTTP-only cookie without the `secure` flag or any CSRF protection, making session theft and cross-site request forgery more feasible when deployed over HTTP.【F:app/routers/auth.py†L24-L114】
- The default LLM provider is seeded with a specific model/version at startup; without migrations or an idempotent guard, version changes or multi-instance deployments could create drift across nodes.【F:app/main.py†L55-L85】

## Recommendations
1. Require JWT secret, encryption key, and admin credentials to be supplied through the environment; refuse startup when defaults are detected, and avoid creating the admin automatically in production builds.【F:app/config.py†L8-L47】【F:app/main.py†L55-L85】
2. Harden session handling by marking cookies as `secure`, shortening lifetime, and adding CSRF tokens (e.g., double-submit) for cookie-authenticated endpoints.【F:app/routers/auth.py†L24-L114】
3. Move bootstrap data (default admin, LLM provider) into migrations or a repeatable seed script with uniqueness guards so clustered deployments remain consistent and the app lifecycle stays lean.【F:app/main.py†L55-L85】
