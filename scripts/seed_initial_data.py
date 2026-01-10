
import sys
import os

# Ensure app directory is in path
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.config import get_settings
from app.utils.crypto import encrypt_value

# Import all models to ensure registry is populated
# Import specific model modules first to define classes
import app.models_chat
import app.models_remediation
import app.models_knowledge
import app.models_troubleshooting
import app.models_agent
import app.models_revive
import app.models_application
import app.models_dashboards
import app.models_group
import app.models_itsm
import app.models_learning
import app.models_runbook_acl
import app.models_scheduler

# Then import the base models
from app.models import User, LLMProvider
from app.models_remediation import Runbook, RunbookStep

def seed_data():
    db = SessionLocal()
    settings = get_settings()
    
    try:
        print("Starting data seeding...")
        
        # 1. Seed LLM Providers
        if settings.openai_api_key:
            print("Checking OpenAI provider...")
            exists = db.query(LLMProvider).filter(LLMProvider.provider_type == 'openai').first()
            if not exists:
                print("Seeding OpenAI (gpt-4o)...")
                provider = LLMProvider(
                    name="OpenAI GPT-4o",
                    provider_type="openai",
                    model_id="gpt-4o",
                    api_key_encrypted=encrypt_value(settings.openai_api_key),
                    is_default=True,
                    is_enabled=True,
                    config_json={"temperature": 0.5}
                )
                db.add(provider)
        
        if settings.anthropic_api_key:
            print("Checking Anthropic provider...")
            exists = db.query(LLMProvider).filter(LLMProvider.provider_type == 'anthropic').first()
            if not exists:
                print("Seeding Anthropic (claude-3-5-sonnet)...")
                provider = LLMProvider(
                    name="Anthropic Claude 3.5 Sonnet",
                    provider_type="anthropic",
                    model_id="claude-3-5-sonnet-20240620",
                    api_key_encrypted=encrypt_value(settings.anthropic_api_key),
                    is_default=False,
                    is_enabled=True,
                    config_json={"temperature": 0.5}
                )
                db.add(provider)

        # 2. Seed Sample Runbooks
        if db.query(Runbook).count() == 0:
            print("Seeding sample runbooks...")
            rb1 = Runbook(
                name="Restart Service",
                description="Standard procedure to restart a failing systemd service.",
                category="Remediation",
                steps=[
                    RunbookStep(step_order=1, name="Check Status", command_linux="systemctl status {{ service_name }}", step_type="command"),
                    RunbookStep(step_order=2, name="Restart", command_linux="sudo systemctl restart {{ service_name }}", step_type="command"),
                    RunbookStep(step_order=3, name="Verify", command_linux="systemctl is-active {{ service_name }}", step_type="command")
                ],
                enabled=True
            )
            
            rb2 = Runbook(
                name="Clean Disk Space",
                description="Clear temp files and rotate logs.",
                category="Maintenance",
                steps=[
                    RunbookStep(step_order=1, name="Check Usage", command_linux="df -h /", step_type="command"),
                    RunbookStep(step_order=2, name="Clean Tmp", command_linux="rm -rf /tmp/*", step_type="command")
                ],
                enabled=True
            )
            db.add(rb1)
            db.add(rb2)
            
        db.commit()
        print("Seeding completed successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
