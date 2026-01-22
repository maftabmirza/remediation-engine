import sys
import os
sys.path.append(os.getcwd())
import logging

from alembic.config import Config
from alembic import command

# Setup logging to see errors
logging.basicConfig(level=logging.INFO) # INFO is usually enough
logger = logging.getLogger("alembic")
logger.setLevel(logging.DEBUG)

def run_upgrade():
    alembic_cfg = Config("alembic.ini")
    # env var is already set in shell
    try:
        command.upgrade(alembic_cfg, "head")
        print("Upgrade successful")
        
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
