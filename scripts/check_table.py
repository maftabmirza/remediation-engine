from sqlalchemy import create_engine, inspect
import os

url = "postgresql://aiops:aiops_secure_password@localhost:5432/aiops"
engine = create_engine(url)
insp = inspect(engine)
from sqlalchemy import text
with engine.connect() as conn:
    # Check Atlas migration status
    try:
        result = conn.execute(text("SELECT * FROM atlas_schema_revisions"))
        print("Atlas Migration Version:", result.fetchall())
    except Exception as e:
        print(f"Atlas table not found (might be fresh install): {e}")

print("Tables:", insp.get_table_names())


