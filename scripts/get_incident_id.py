
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent dir to path to import app config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
# Import models to ensure they are registered
import app.models
from sqlalchemy import create_engine, text

def get_id():
    settings = get_settings()
    db_url = settings.database_url.replace("postgres:", "localhost:")
    db_url = db_url.replace("@postgres", "@localhost")
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id FROM incident_events LIMIT 1"))
        row = result.fetchone()
        
        if row:
            print(f"INCIDENT_ID={row[0]}")
        else:
            print("No incidents found")

if __name__ == "__main__":
    get_id()
