from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.models_itsm import ITSMIntegration
from app.database import Base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aiops:aiops_secure_password@localhost:5432/aiops")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_integrations():
    db = SessionLocal()
    try:
        integrations = db.query(ITSMIntegration).all()
        print(f"Found {len(integrations)} integrations")
        for integration in integrations:
            print(f"- ID: {integration.id}")
            print(f"  Name: {integration.name}")
            print(f"  Type: {integration.connector_type}")
            print(f"  Enabled: {integration.is_enabled}")
            print(f"  Last Sync: {integration.last_sync}")
    finally:
        db.close()

if __name__ == "__main__":
    check_integrations()
