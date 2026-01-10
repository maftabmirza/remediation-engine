
from app.database import SessionLocal
from sqlalchemy import text

def check():
    db = SessionLocal()
    try:
        # Check all providers
        providers = db.execute(text("SELECT id, name, model_id, api_key_encrypted IS NOT NULL as has_key FROM llm_providers")).fetchall()
        print(f"LLM Providers ({len(providers)}):")
        for p in providers:
            print(f"  {p[0]} | {p[1]} | {p[2]} | has_key={p[3]}")
            
        # Check recent chat sessions
        sessions = db.execute(text("SELECT id, llm_provider_id FROM chat_sessions ORDER BY created_at DESC LIMIT 3")).fetchall()
        print(f"\nRecent Chat Sessions:")
        for s in sessions:
            print(f"  Session: {s[0]} | Provider ID: {s[1]}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check()
