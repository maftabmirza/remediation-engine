#!/usr/bin/env python3
"""
Check LLM Provider Configuration
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import SessionLocal
from app.models import LLMProvider
from app.services.encryption import decrypt_value
from app.config import get_settings

def main():
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("LLM PROVIDER CONFIGURATION CHECK")
        print("=" * 80)
        
        # Check environment settings
        settings = get_settings()
        print("\n1. ENVIRONMENT VARIABLES:")
        print(f"   ANTHROPIC_API_KEY: {'SET' if settings.anthropic_api_key else 'NOT SET'}")
        if settings.anthropic_api_key:
            print(f"      Prefix: {settings.anthropic_api_key[:15]}...")
        print(f"   OPENAI_API_KEY: {'SET' if settings.openai_api_key else 'NOT SET'}")
        if settings.openai_api_key:
            print(f"      Prefix: {settings.openai_api_key[:15]}...")
        
        # Check database providers
        print("\n2. DATABASE PROVIDERS:")
        providers = db.query(LLMProvider).all()
        
        if not providers:
            print("   NO PROVIDERS FOUND IN DATABASE!")
        else:
            for p in providers:
                print(f"\n   Provider: {p.name}")
                print(f"   - ID: {p.id}")
                print(f"   - Type: {p.provider_type}")
                print(f"   - Model: {p.model_id}")
                print(f"   - Enabled: {p.is_enabled}")
                print(f"   - Default: {p.is_default}")
                print(f"   - Has Encrypted Key: {bool(p.api_key_encrypted)}")
                
                if p.api_key_encrypted:
                    try:
                        decrypted_key = decrypt_value(p.api_key_encrypted)
                        print(f"   - Decrypted Key: {decrypted_key[:15]}..." if len(decrypted_key) > 15 else f"   - Decrypted Key: {decrypted_key}")
                    except Exception as e:
                        print(f"   - ⚠️ Decryption Failed: {e}")
                else:
                    print(f"   - Will use environment variable")
        
        # Check for issues
        print("\n3. POTENTIAL ISSUES:")
        openai_providers = [p for p in providers if p.provider_type == "openai" and p.is_enabled]
        anthropic_providers = [p for p in providers if p.provider_type == "anthropic" and p.is_enabled]
        
        if openai_providers:
            print(f"\n   ✓ Found {len(openai_providers)} enabled OpenAI provider(s)")
            for p in openai_providers:
                # Check if it has a key
                if p.api_key_encrypted:
                    try:
                        key = decrypt_value(p.api_key_encrypted)
                        if not key or len(key) < 10:
                            print(f"   ⚠️ Provider '{p.name}' has invalid encrypted key")
                    except:
                        print(f"   ⚠️ Provider '{p.name}' key decryption failed")
                elif not settings.openai_api_key:
                    print(f"   ⚠️ Provider '{p.name}' has no encrypted key and OPENAI_API_KEY env var not set")
        else:
            print("   ⚠️ No enabled OpenAI providers found")
        
        if anthropic_providers:
            print(f"\n   ✓ Found {len(anthropic_providers)} enabled Anthropic provider(s)")
            for p in anthropic_providers:
                if p.api_key_encrypted:
                    try:
                        key = decrypt_value(p.api_key_encrypted)
                        if not key or len(key) < 10:
                            print(f"   ⚠️ Provider '{p.name}' has invalid encrypted key")
                    except:
                        print(f"   ⚠️ Provider '{p.name}' key decryption failed")
                elif not settings.anthropic_api_key:
                    print(f"   ⚠️ Provider '{p.name}' has no encrypted key and ANTHROPIC_API_KEY env var not set")
        
        print("\n" + "=" * 80)
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
