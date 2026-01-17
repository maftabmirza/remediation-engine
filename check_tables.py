
from app.database import SessionLocal
from sqlalchemy import text

def check_data():
    db = SessionLocal()
    try:
        tables = [
            'alerts', 'server_credentials', 'runbooks', 'users', 
            'llm_providers', 'dashboards', 'panels', 'roles',
            'playlists', 'knowledge_sources', 'chat_sessions',
            'file_versions', 'file_backups', 'change_sets', 'change_items'
        ]
        
        print("Table Data Counts:")
        print("=" * 40)
        for table in tables:
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"  {table}: {result}")
            except Exception as e:
                db.rollback()
                print(f"  {table}: ERROR - {e}")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_data()
