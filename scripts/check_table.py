from sqlalchemy import create_engine, inspect
import os

url = "postgresql://aiops:aiops_secure_password@localhost:5432/aiops"
engine = create_engine(url)
insp = inspect(engine)
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM alembic_version"))
    print("Alembic Version:", result.fetchall())

print("Tables:", insp.get_table_names())


