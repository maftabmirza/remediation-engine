
from app.database import SessionLocal
from sqlalchemy import text

def fix_model():
    db = SessionLocal()
    try:
        # Use the same model as local (Claude 3 Haiku which works)
        db.execute(text("""
            UPDATE llm_providers 
            SET model_id = 'anthropic/claude-3-haiku-20240307' 
            WHERE provider_type = 'anthropic'
        """))
        db.commit()
        print("Model ID updated to anthropic/claude-3-haiku-20240307 (matching local)")
        
        # Verify
        result = db.execute(text("SELECT model_id FROM llm_providers WHERE provider_type = 'anthropic'")).fetchone()
        print(f"Verified model: {result[0]}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_model()
