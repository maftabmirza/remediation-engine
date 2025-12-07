import os
import glob
import re
from sqlalchemy import text
from app.database import engine

def split_sql_statements(sql_content):
    """
    Split SQL content into statements by semicolon, respecting quotes.
    """
    statements = []
    current_statement = []
    in_quote = False
    quote_char = None
    
    # Iterate char by char to handle quotes
    i = 0
    length = len(sql_content)
    while i < length:
        char = sql_content[i]
        
        if in_quote:
            current_statement.append(char)
            if char == quote_char:
                # Handle escaped quotes like 'It''s'
                if i + 1 < length and sql_content[i+1] == quote_char:
                    current_statement.append(sql_content[i+1])
                    i += 1
                else:
                    in_quote = False
                    quote_char = None
        else:
            if char == "'" or char == '"':
                in_quote = True
                quote_char = char
                current_statement.append(char)
            elif char == ';':
                # End of statement
                stmt = "".join(current_statement).strip()
                if stmt:
                    statements.append(stmt)
                current_statement = []
            else:
                current_statement.append(char)
        i += 1
        
    # Append last statement if any
    stmt = "".join(current_statement).strip()
    if stmt:
        statements.append(stmt)
        
    return statements

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
                statements = split_sql_statements(sql_content)
                for statement in statements:
                    if statement.strip():
                        connection.execute(text(statement))
                connection.commit()
                print(f"Successfully applied {filename}")
            except Exception as e:
                # Check if it's "relation already exists" or "column already exists" which are safe to ignore
                # if the script uses IF NOT EXISTS (which ours do).
                # But simple python parser execution error might fail whole block.
                # Actually, our SQL files use IF NOT EXISTS, so running them should be fine *if* parsed correctly.
                # If an error specifically says "already exists", we might want to log warn and separate.
                # For now, let's assume valid Parse = Valid Run because of idempotent SQL.
                print(f"Error applying {filename}: {e}")
                connection.rollback()
                # We raise to stop on actual errors
                raise e

    print("All migrations completed successfully.")

if __name__ == "__main__":
    run_migrations()
