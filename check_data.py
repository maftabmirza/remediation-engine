
from app.database import SessionLocal
from sqlalchemy import text

def check_data():
    db = SessionLocal()
    try:
        llm = db.execute(text("SELECT count(*) FROM llm_providers")).scalar()
        runbooks = db.execute(text("SELECT count(*) FROM runbooks")).scalar()
        users = db.execute(text("SELECT count(*) FROM users")).scalar()
        
        print(f"LLM Providers: {llm}")
        print(f"Runbooks: {runbooks}")
        print(f"Users: {users}")
    except Exception as e:
        print(f"Error checking data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_data()
