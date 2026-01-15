
from app.database import SessionLocal
from sqlalchemy import text

def compare_schema():
    db = SessionLocal()
    try:
        # Get all tables
        tables = db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)).fetchall()
        
        print(f"Total tables: {len(tables)}")
        print("=" * 60)
        
        for (table_name,) in tables:
            # Get column count
            cols = db.execute(text(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = '{table_name}'
                ORDER BY ordinal_position
            """)).fetchall()
            print(f"{table_name}: {len(cols)} columns")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    compare_schema()
