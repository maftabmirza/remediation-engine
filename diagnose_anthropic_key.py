#!/usr/bin/env python3
"""
Diagnostic script to check Anthropic API key configuration and validity.
"""
import os
import sys
import asyncio

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.config import get_settings
from app.database import SessionLocal
from app.models import LLMProvider
from app.services.encryption import decrypt_value


async def test_anthropic_key(api_key: str):
    """Test if the Anthropic API key is valid."""
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key, timeout=10.0)
        
        # Try a simple API call
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "Say hello"}]
        )
        
        return True, "API key is valid!"
    except anthropic.AuthenticationError as e:
        return False, f"Authentication failed: {e}"
    except Exception as e:
        return False, f"Error testing key: {e}"


def main():
    print("=" * 80)
    print("ANTHROPIC API KEY DIAGNOSTIC")
    print("=" * 80)
    
    # Check environment variable
    settings = get_settings()
    env_key = settings.anthropic_api_key
    
    print(f"\n1. Environment Variable (ANTHROPIC_API_KEY):")
    if env_key:
        print(f"   ✓ Set (length: {len(env_key)})")
        print(f"   Prefix: {env_key[:15]}..." if len(env_key) > 15 else f"   Full: {env_key}")
    else:
        print("   ✗ NOT SET")
    
    # Check database providers
    print(f"\n2. Database LLM Providers:")
    db = SessionLocal()
    try:
        providers = db.query(LLMProvider).filter(
            LLMProvider.provider_type == "anthropic"
        ).all()
        
        if not providers:
            print("   ✗ No Anthropic providers found in database")
        else:
            for idx, provider in enumerate(providers, 1):
                print(f"\n   Provider #{idx}:")
                print(f"   - Name: {provider.name}")
                print(f"   - Model: {provider.model_id}")
                print(f"   - Enabled: {provider.is_enabled}")
                print(f"   - Default: {provider.is_default}")
                print(f"   - Has encrypted key: {bool(provider.api_key_encrypted)}")
                
                if provider.api_key_encrypted:
                    try:
                        decrypted = decrypt_value(provider.api_key_encrypted)
                        print(f"   - Decrypted key length: {len(decrypted)}")
                        print(f"   - Decrypted key prefix: {decrypted[:15]}..." if len(decrypted) > 15 else f"   - Full: {decrypted}")
                    except Exception as e:
                        print(f"   - ✗ Failed to decrypt: {e}")
    finally:
        db.close()
    
    # Test the key
    print(f"\n3. Testing API Key Validity:")
    if env_key:
        print("   Testing environment variable key...")
        is_valid, message = asyncio.run(test_anthropic_key(env_key))
        if is_valid:
            print(f"   ✓ {message}")
        else:
            print(f"   ✗ {message}")
    else:
        print("   ✗ No key to test")
    
    # Recommendations
    print(f"\n" + "=" * 80)
    print("RECOMMENDATIONS:")
    print("=" * 80)
    
    if not env_key:
        print("1. Set ANTHROPIC_API_KEY in your .env file")
        print("   Format: ANTHROPIC_API_KEY=sk-ant-api03-...")
    elif env_key and not asyncio.run(test_anthropic_key(env_key))[0]:
        print("1. Your API key appears to be invalid or expired")
        print("   - Verify the key at https://console.anthropic.com/")
        print("   - Generate a new key if needed")
        print("   - Update the .env file with the new key")
        print("   - Restart the application")
    
    db = SessionLocal()
    try:
        providers = db.query(LLMProvider).filter(
            LLMProvider.provider_type == "anthropic",
            LLMProvider.is_enabled == True
        ).all()
        
        if providers:
            print("\n2. Update database provider keys:")
            print("   - Go to Settings > LLM Providers in the UI")
            print("   - Update the API key for each Anthropic provider")
            print("   - Or run: python scripts/update_provider_key.py")
    finally:
        db.close()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
