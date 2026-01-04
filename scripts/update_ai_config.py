import os
import sys
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base
from app.models import User
# Import all models to satisfy registry
import app.models_chat
import app.models_application
import app.models_agent
import app.models_ai_helper
import app.models_application
import app.models_chat
import app.models_dashboards
import app.models_group
import app.models_itsm
import app.models_knowledge
import app.models_learning
import app.models_remediation
import app.models_runbook_acl
import app.models_scheduler
import app.models_troubleshooting
from app.models_ai_helper import AIHelperConfig

print("Starting AI Config Update...")

# Get database URL from environment or default
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aiops:aiops_secure_password@postgres:5432/aiops")

# Create session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    print("Fetching allowed_actions config...")
    config = db.query(AIHelperConfig).filter(
        AIHelperConfig.config_key == "allowed_actions"
    ).first()

    if config:
        print(f"Current allowed actions: {config.config_value}")
        current_actions = config.config_value
        
        if "chat" not in current_actions:
            print("Adding 'chat' to allowed actions...")
            current_actions.append("chat")
            
            # Update database - Use flag_modified
            config.config_value = current_actions
            flag_modified(config, "config_value")
            
            db.commit()
            print("Successfully updated allowed_actions.")
        else:
            print("'chat' action already enabled.")
    else:
        print("Config 'allowed_actions' not found in database. Creating it...")
        # Create default config if missing
        default_actions = [
            "suggest_form_values",
            "search_knowledge",
            "explain_concept",
            "show_example",
            "validate_input",
            "generate_preview",
            "chat"
        ]
        
        new_config = AIHelperConfig(
            config_key="allowed_actions",
            config_value=default_actions,
            description="List of allowed AI actions",
            enabled=True
        )
        db.add(new_config)
        db.commit()
        print("Created 'allowed_actions' config.")

    # Verify
    config = db.query(AIHelperConfig).filter(
        AIHelperConfig.config_key == "allowed_actions"
    ).first()
    print(f"Final allowed actions: {config.config_value}")

except Exception as e:
    print(f"Error: {e}")
    db.rollback()
finally:
    db.close()
    print("Done.")
