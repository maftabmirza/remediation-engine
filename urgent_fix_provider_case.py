#!/usr/bin/env python3
"""
URGENT FIX: Normalize all provider_type values to lowercase
"""
import sys
import os

def main():
    # Use raw SQL to avoid model loading issues
    import psycopg2
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            database=os.getenv('POSTGRES_DB', 'aiops'),
            user=os.getenv('POSTGRES_USER', 'aiops'),
            password=os.getenv('POSTGRES_PASSWORD', 'aiops')
        )
        
        cursor = conn.cursor()
        
        print("Fixing provider_type case sensitivity issue...")
        print("=" * 80)
        
        # Get current providers
        cursor.execute("SELECT id, name, provider_type FROM llm_providers")
        providers = cursor.fetchall()
        
        if not providers:
            print("❌ No providers found in database!")
            return
        
        fixed = 0
        for provider_id, name, provider_type in providers:
            old_type = provider_type
            new_type = (provider_type or "").lower().strip()
            
            if old_type != new_type:
                print(f"\nProvider: {name}")
                print(f"  Before: provider_type = '{old_type}'")
                print(f"  After:  provider_type = '{new_type}'")
                
                cursor.execute(
                    "UPDATE llm_providers SET provider_type = %s WHERE id = %s",
                    (new_type, provider_id)
                )
                fixed += 1
            else:
                print(f"\n✅ Provider '{name}' already correct: {provider_type}")
        
        if fixed > 0:
            conn.commit()
            print("\n" + "=" * 80)
            print(f"✅ Fixed {fixed} provider(s)")
            print("\n⚠️  RESTART REQUIRED:")
            print("   docker-compose restart engine")
        else:
            print("\n" + "=" * 80)
            print("✅ All providers already have correct case")
        
        cursor.close()
        conn.close()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
