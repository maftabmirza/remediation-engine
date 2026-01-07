---
trigger: always_on
---

Database Migration Verification Checklist
To prevent deployment failures where the Local DB works but the Production Deployment fails, perform these 4 checks before every commit.

1. The "Drift" Check (Code vs. Local DB)
Goal: Ensure your local database matches your Python models. Command:

docker-compose exec remediation-engine alembic check
Result: Should say "No new upgrade operations detected."
If it fails: It means you changed 
models.py
 but didn't apply it to your local DB. Run alembic revision --autogenerate + alembic upgrade head.
2. The "Missing File" Check (Migration vs. Fresh DB) 🌟 CRITICAL
Goal: Ensure existing migration files are sufficient to rebuild the DB from scratch. (This is what we missed!). Why: Your local DB might have tables created manually or by deleted migrations. Only a fresh build proves the files are correct. Steps:

Spin up a temp DB (e.g., specific test container or during CI).
Run Migrations: alembic upgrade head.
Verify Schema: Check if critical tables (e.g., ai_helper_sessions) exist. Manual Quick-Check: Review the 
alembic/versions
 directory. Do you see a file that explicitly does op.create_table('new_table_name')? If not, the migration is missing.
3. The "Head" Check
Goal: Ensure there is a single, clear path for the database to upgrade. Command:

docker-compose exec remediation-engine alembic heads
Result: Should list exactly one revision ID representing the "head".
If it fails: (Lists multiple IDs) You have a fork (e.g., from merging branches). run alembic merge heads.
4. The "Downgrade" Test (Optional but Recommended)
Goal: Ensure your migration can be rolled back safely. Command:

docker-compose exec remediation-engine alembic downgrade -1
docker-compose exec remediation-engine alembic upgrade head
Result: Should succeed without errors. Catch bugs where down_revision logic is broken.
🚨 Golden Rule
"Currently Working Local DB" ≠ "Correct Migration Scripts" Always assume your local database is "dirty". Trust only what alembic upgrade head produces on a fresh container.

