from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from app.models_itsm import ChangeEvent

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aiops:aiops_secure_password@localhost:5432/aiops")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_changes():
    db = SessionLocal()
    try:
        changes = db.query(ChangeEvent).order_by(ChangeEvent.timestamp.desc()).limit(10).all()
        print(f"Found {len(changes)} recent changes:")
        for change in changes:
            print(f"- {change.change_id}: {change.description[:50]}... ({change.timestamp})")
    finally:
        db.close()

if __name__ == "__main__":
    check_changes()
