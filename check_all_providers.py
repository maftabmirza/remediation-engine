
# Import all models first
import app.models_chat
import app.models_remediation
import app.models_revive

from app.database import SessionLocal
from app.models import LLMProvider
from app.models_chat import ChatSession
from app.services.llm_service import get_api_key_for_provider
from sqlalchemy import text

def check_all_providers():
    db = SessionLocal()
    
    try:
        # List all providers
        providers = db.query(LLMProvider).all()
        print(f"Total providers in DB: {len(providers)}")
        for p in providers:
            key = get_api_key_for_provider(p)
            key_preview = key[:20] if key else "NONE"
            print(f"  ID: {p.id} | Name: {p.name} | Key: {key_preview}...")
            
        # Check active chat sessions
        sessions = db.execute(text("""
            SELECT cs.id, cs.llm_provider_id, lp.name, lp.api_key_encrypted IS NOT NULL as has_key
            FROM chat_sessions cs
            LEFT JOIN llm_providers lp ON cs.llm_provider_id = lp.id
            ORDER BY cs.created_at DESC
            LIMIT 5
        """)).fetchall()
        
        print(f"\nRecent chat sessions:")
        for s in sessions:
            print(f"  Session: {s[0]} | Provider ID: {s[1]} | Provider: {s[2]} | Has Key: {s[3]}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_all_providers()
