from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import sys
import json

# Add current directory to path
sys.path.append(os.getcwd())

from app.models_itsm import ITSMIntegration
from app.utils.crypto import decrypt_value

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aiops:aiops_secure_password@localhost:5432/aiops")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def dump_config():
    db = SessionLocal()
    try:
        integrations = db.query(ITSMIntegration).filter(ITSMIntegration.name == "JIRA").all()
        for integration in integrations:
            print(f"Integration: {integration.name}")
            try:
                decrypted = decrypt_value(integration.config_encrypted)
                config = json.loads(decrypted)
                print(f"Config: {json.dumps(config, indent=2)}")
            except Exception as e:
                print(f"Error decrypting: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    dump_config()
