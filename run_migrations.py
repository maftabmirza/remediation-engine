import os
import glob
import re
from sqlalchemy import text
from app.database import engine

def split_sql_statements(sql_content):
    """
    Split SQL content into statements by semicolon, respecting quotes and dollar-quotes.
    """
    statements = []
    current_statement = []
    in_quote = False
    quote_char = None
    in_dollar_quote = False
    dollar_quote_tag = None
    
    i = 0
    length = len(sql_content)
    while i < length:
        char = sql_content[i]
        
        # Handle Dollar Quotes (e.g., $$ or $tag$)
        if not in_quote and not in_dollar_quote:
            if char == '$':
                # Check for start of dollar quote
                match = re.match(r'\$([^$]*)\$', sql_content[i:])
                if match:
                    tag = match.group(0)
                    in_dollar_quote = True
                    dollar_quote_tag = tag
                    current_statement.append(tag)
                    i += len(tag)
                    continue

        if in_dollar_quote:
            current_statement.append(char)
            # Check for end of dollar quote
            if char == '$':
                pass # Optimization: only check match if potentially closing
                # But we need to check full tag match ending at i
                # E.g. tag='$$', we just appended '$', check if it closes
                # Simplest is lookahead or keep buffer.
                # Actually, easier: if we see $, check if it matches tag
                tag_len = len(dollar_quote_tag)
                # Check if current_statement ends with tag
                # Since we append char one by one, we need to be careful
                # Alternative: Let's regex search from current pos? No, we are iterating.
                
                # Check if the sequence we just built ends with the tag
                # But we haven't built it fully in current_statement if we're iterating?
                # Actually current_statement is a list of chars.
                
                # Let's peek backwards:
                # We need to see if sql_content[i-tag_len+1 : i+1] == tag
                # e.g tag=$$, len=2. i points to 2nd $. content[i-1:i+1]
                start_check = i - tag_len + 1
                if start_check >= 0:
                    potential_tag = sql_content[start_check : i+1]
                    if potential_tag == dollar_quote_tag:
                         in_dollar_quote = False
                         dollar_quote_tag = None
            i += 1
            continue

        # Handle Standard Quotes
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
            i += 1
            continue
            
        # Normal State
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
        elif char == '-' and i + 1 < length and sql_content[i+1] == '-':
             # Line comment -- 
             # We should consume until newline to avoid issues? 
             # For splitting, comments are fine to include, unless they contain ;
             # But ; in comment ends statement? Standard SQL: yes usually.
             # But safer to ignore ; in comments.
             # Let's implement comment skipping (standard --)
             current_statement.append(char) # -
             current_statement.append(sql_content[i+1]) # -
             i += 2
             while i < length and sql_content[i] != '\n':
                 current_statement.append(sql_content[i])
                 i += 1
             continue # Loop re-evaluates at \n
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
