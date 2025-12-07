
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

sql = """
INSERT INTO command_blocklist (pattern, pattern_type, os_type, description, severity) VALUES
(':\(\)\{\s*:\|:&\s*\};:', 'regex', 'linux', 'Fork bomb', 'critical');

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';
"""

print(f"Testing SQL: {sql}")
stmts = split_sql_statements(sql)
print(f"Found {len(stmts)} statements.")
for idx, s in enumerate(stmts):
    print(f"--- Statement {idx} ---")
    print(s)
    print("-----------------------")
