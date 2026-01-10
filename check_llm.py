
from app.database import SessionLocal
from sqlalchemy import text

def check_llm():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT id, name, provider_type, model_id, is_default, is_enabled, api_key_encrypted IS NOT NULL as has_key
            FROM llm_providers
        """)).fetchall()
        
        if not result:
            print("No LLM providers found!")
            return
        
        for row in result:
            print(f"ID: {row[0]}")
            print(f"  Name: {row[1]}")
            print(f"  Type: {row[2]}")
            print(f"  Model: {row[3]}")
            print(f"  Is Default: {row[4]}")
            print(f"  Is Enabled: {row[5]}")
            print(f"  Has API Key: {row[6]}")
            print()
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_llm()
