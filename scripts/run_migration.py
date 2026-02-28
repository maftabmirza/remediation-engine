"""
Migration runner using Atlas (replaced Alembic).
Use this script to run Atlas migrations from command line.

Usage:
    python scripts/run_migration.py

Or run Atlas directly:
    atlas migrate apply --url "$DATABASE_URL" --dir "file://atlas/migrations"
"""
import sys
import os
import subprocess
sys.path.append(os.getcwd())
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("atlas-migration")
logger.setLevel(logging.DEBUG)

def run_upgrade():
    """Run Atlas migrations."""
    db_url = os.environ.get("DATABASE_URL", "postgresql://aiops:aiops@localhost:5432/aiops")
    
    try:
        # Run Atlas migration
        result = subprocess.run(
            ["atlas", "migrate", "apply", "--url", db_url, "--dir", "file://atlas/migrations"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Migration failed: {result.stderr}")
            return
            
        print("Migration successful")
        print(result.stdout)
        
        # Verify
        from sqlalchemy import create_engine, inspect
        url = os.environ.get("DATABASE_URL")
        print(f"Inspecting URL: {url}")
        engine = create_engine(url)
        insp = inspect(engine)
        tables = insp.get_table_names()
        print(f"Tables after upgrade: {tables}")
        if 'ai_permissions' in tables:
            print("VERIFIED: ai_permissions exists")
        else:
            print("ERROR: ai_permissions MISSING after upgrade")
            
        columns = [c['name'] for c in insp.get_columns('ai_sessions')]
        print(f"ai_sessions columns: {columns}")
        if 'pillar' in columns:
            print("VERIFIED: ai_sessions has pillar column")
        else:
            print("ERROR: ai_sessions MISSING pillar column")


    except Exception as e:

        print(f"Upgrade failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_upgrade()
