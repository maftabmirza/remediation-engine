from app.database import SessionLocal
from app.models import LLMProvider, User
from app.utils.crypto import get_cipher_suite

# Import all models
import app.models_chat
import app.models_knowledge
import app.models_troubleshooting
import app.models_application
import app.models_remediation
import app.models_agent
import app.models_ai_helper
import app.models_dashboards
import app.models_group
import app.models_itsm
import app.models_learning
import app.models_runbook_acl
import app.models_scheduler

import os

db = SessionLocal()
key_str = os.environ.get("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY_HERE")

try:
    print("Encrypting key...")
    encrypted_key = get_cipher_suite().encrypt(key_str.encode()).decode()
except Exception:
    encrypted_key = "ENCRYPTION_FAILED"

provider = db.query(LLMProvider).filter(LLMProvider.provider_type == "anthropic").first()
if not provider:
    print("Creating Anthropic Provider...")
    provider = LLMProvider(
        name="Anthropic Claude 3",
        provider_type="anthropic",
        model_id="claude-3-opus-20240229",
        api_key_encrypted=encrypted_key,
        is_default=False, 
        is_enabled=True,
        config_json={"temperature": 0.5}
    )
    db.add(provider)
    db.commit()
    print("Anthropic Provider created.")
else:
    print("Anthropic Provider exists.")

db.close()
