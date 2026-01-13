from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # 1. Check what we have
    print("Current Providers:")
    result = conn.execute(text("SELECT id, name, model_id, is_default FROM llm_providers"))
    for row in result:
        print(f"ID: {row[0]}, Name: {row[1]}, Model: {row[2]}, Default: {row[3]}")
        
    # 2. Update the mismatched provider
    # If name implies Sonnet but model is Haiku, let's make it Sonnet
    print("\nUpdating provider...")
    
    # Update specifically the one named 'Anthropic Claude 3.5 Sonnet' to use the correct model ID
    update_query = text("""
        UPDATE llm_providers 
        SET model_id = 'claude-3-5-sonnet-20240620'
        WHERE name LIKE '%Sonnet%' AND model_id LIKE '%haiku%'
    """)
    result = conn.execute(update_query)
    print(f"Updated {result.rowcount} rows.")
    
    conn.commit()
    
    # 3. Verify
    print("\nNew State:")
    result = conn.execute(text("SELECT id, name, model_id, is_default FROM llm_providers"))
    for row in result:
        print(f"ID: {row[0]}, Name: {row[1]}, Model: {row[2]}, Default: {row[3]}")
