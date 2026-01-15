
from app.database import SessionLocal
from app.utils.crypto import decrypt_value
from sqlalchemy import text

def test_key():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT api_key_encrypted FROM llm_providers LIMIT 1")).fetchone()
        if result and result[0]:
            encrypted = result[0]
            print(f"Encrypted key exists: {len(encrypted)} chars")
            print(f"First 50 chars: {encrypted[:50]}...")
            
            try:
                decrypted = decrypt_value(encrypted)
                if decrypted:
                    print(f"Decryption SUCCESS! Key starts with: {decrypted[:15]}...")
                else:
                    print("Decryption returned None")
            except Exception as e:
                print(f"Decryption FAILED: {e}")
        else:
            print("No encrypted key in database")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_key()
