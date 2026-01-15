
from app.database import SessionLocal
from sqlalchemy import text

def fix_default():
    db = SessionLocal()
    try:
        db.execute(text("UPDATE llm_providers SET is_default = true WHERE is_enabled = true"))
        db.commit()
        print("Updated default provider successfully!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_default()
