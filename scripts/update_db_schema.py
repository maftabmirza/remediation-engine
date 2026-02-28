
import os
import sys
from sqlalchemy import create_engine, text

# Add parent dir to path to import app config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings

def update_schema():
    settings = get_settings()
    # Adjust for local execution if needed
    db_url = settings.database_url.replace("postgres:", "localhost:")
    db_url = db_url.replace("@postgres", "@localhost")
    
    print(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        with conn.begin():
            print("Checking/Adding columns to incident_events...")
            
            # Helper to add column if not exists
            def add_column(column_name, column_type, default=None):
                try:
                    conn.execute(text(f"ALTER TABLE incident_events ADD COLUMN {column_name} {column_type}"))
                    if default is not None:
                         conn.execute(text(f"ALTER TABLE incident_events ALTER COLUMN {column_name} SET DEFAULT {default}"))
                    print(f"Added column {column_name}")
                except Exception as e:
                    if "already exists" in str(e):
                        print(f"Column {column_name} already exists")
                    else:
                        print(f"Error adding {column_name}: {e}")

            add_column("analyzed", "BOOLEAN DEFAULT FALSE")
            add_column("analyzed_at", "TIMESTAMP WITH TIME ZONE")
            add_column("analyzed_by", "UUID")
            add_column("ai_analysis", "TEXT")
            add_column("recommendations_json", "JSONB DEFAULT '[]'")
            add_column("llm_provider_id", "UUID")
            add_column("analysis_count", "INTEGER DEFAULT 0")
            
            print("Schema update completed.")

if __name__ == "__main__":
    update_schema()
