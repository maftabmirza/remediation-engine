
# Import all models first
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

from app.database import SessionLocal
from app.models import LLMProvider
from app.services.llm_service import get_api_key_for_provider
from app.config import get_settings

def test_full_flow():
    db = SessionLocal()
    settings = get_settings()
    
    try:
        # Get provider from DB (same as chat does)
        provider = db.query(LLMProvider).filter(
            LLMProvider.is_default == True,
            LLMProvider.is_enabled == True
        ).first()
        
        if not provider:
            print("No default provider found!")
            return
            
        print(f"Provider: {provider.name}")
        print(f"Has encrypted key: {provider.api_key_encrypted is not None}")
        
        # Call the same function that chat uses
        api_key = get_api_key_for_provider(provider)
        
        if api_key:
            print(f"Key returned (first 20 chars): {api_key[:20]}...")
            print(f"Is placeholder?: {'sk-ant-your-key-here' in api_key}")
        else:
            print("Key returned: None (will fallback to env var)")
            
        print(f"Env var key: {settings.anthropic_api_key}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_full_flow()
