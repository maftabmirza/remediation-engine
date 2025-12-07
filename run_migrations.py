import os
import glob
from sqlalchemy import text
from app.database import engine

def run_migrations():
    print("Running database migrations...")
    
    # Get all .sql files in migrations directory
    migration_dir = os.path.join(os.path.dirname(__file__), "migrations")
    sql_files = sorted(glob.glob(os.path.join(migration_dir, "*.sql")))
    
    if not sql_files:
        print("No migration files found.")
        return

    with engine.connect() as connection:
        for file_path in sql_files:
            filename = os.path.basename(file_path)
            print(f"Applying {filename}...")
            
            with open(file_path, "r", encoding="utf-8") as f:
                sql_content = f.read()
                
            try:
                # Split usage of transactions if needed, but for now assuming individual scripts are safe
                # Most scripts use IF NOT EXISTS so re-running is safe
                statements = sql_content.split(';')
                for statement in statements:
                    if statement.strip():
                        connection.execute(text(statement))
                connection.commit()
                print(f"Successfully applied {filename}")
            except Exception as e:
                print(f"Error applying {filename}: {e}")
                connection.rollback()
                # Decide if we should stop or continue. Failing safely is better.
                raise e

    print("All migrations completed successfully.")

if __name__ == "__main__":
    run_migrations()
