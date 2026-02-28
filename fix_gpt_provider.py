#!/usr/bin/env python3
"""
Quick fix script for GPT provider authentication issues.
This script will:
1. Check all providers
2. Fix any with incorrect provider_type
3. Verify API keys are accessible
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
    settings = get_settings()
    
    try:
        print("=" * 80)
        print("GPT PROVIDER FIX SCRIPT")
        print("=" * 80)
        
        providers = db.query(LLMProvider).all()
        
        if not providers:
            print("\n❌ No providers found in database!")
            print("   Please add a provider through Settings > LLM Providers")
            return
        
        fixed_count = 0
        issues_found = []
        
        for provider in providers:
            print(f"\n📋 Checking provider: {provider.name}")
            print(f"   Type: {provider.provider_type}")
            print(f"   Model: {provider.model_id}")
            print(f"   Enabled: {provider.is_enabled}")
            
            modified = False
            
            # Check 1: Provider type should be lowercase and trimmed
            if provider.provider_type != provider.provider_type.lower().strip():
                print(f"   🔧 Fixing provider_type: '{provider.provider_type}' -> '{provider.provider_type.lower().strip()}'")
                provider.provider_type = provider.provider_type.lower().strip()
                modified = True
                fixed_count += 1
            
            # Check 2: Model ID shouldn't have provider prefix for OpenAI
            if provider.provider_type == "openai" and "/" in provider.model_id:
                if provider.model_id.startswith("openai/"):
                    old_model = provider.model_id
                    provider.model_id = provider.model_id.replace("openai/", "")
                    print(f"   🔧 Fixing model ID: '{old_model}' -> '{provider.model_id}'")
                    modified = True
                    fixed_count += 1
            
            # Check 3: Anthropic model should be cleaned up
            if provider.provider_type == "anthropic" and "/" in provider.model_id:
                if provider.model_id.startswith("anthropic/"):
                    old_model = provider.model_id
                    provider.model_id = provider.model_id.replace("anthropic/", "")
                    print(f"   🔧 Fixing model ID: '{old_model}' -> '{provider.model_id}'")
                    modified = True
                    fixed_count += 1
            
            # Check 4: Verify API key is accessible
            if provider.api_key_encrypted:
                try:
                    decrypted = decrypt_value(provider.api_key_encrypted)
                    if not decrypted or len(decrypted) < 10:
                        print(f"   ⚠️  WARNING: API key appears invalid (too short or empty)")
                        issues_found.append(f"Provider '{provider.name}' has invalid encrypted key")
                    else:
                        print(f"   ✅ Encrypted API key is valid")
                except Exception as e:
                    print(f"   ❌ ERROR: Cannot decrypt API key: {e}")
                    issues_found.append(f"Provider '{provider.name}' key decryption failed")
            else:
                # Check if environment variable is set
                if provider.provider_type == "openai":
                    if not settings.openai_api_key:
                        print(f"   ⚠️  WARNING: No encrypted key and OPENAI_API_KEY not set")
                        issues_found.append(f"Provider '{provider.name}' has no API key configured")
                    else:
                        print(f"   ✅ Will use OPENAI_API_KEY environment variable")
                elif provider.provider_type == "anthropic":
                    if not settings.anthropic_api_key:
                        print(f"   ⚠️  WARNING: No encrypted key and ANTHROPIC_API_KEY not set")
                        issues_found.append(f"Provider '{provider.name}' has no API key configured")
                    else:
                        print(f"   ✅ Will use ANTHROPIC_API_KEY environment variable")
            
            if modified:
                print(f"   💾 Saving changes...")
        
        # Commit all changes
        if fixed_count > 0:
            db.commit()
            print(f"\n✅ Fixed {fixed_count} issue(s) and saved to database")
        else:
            print(f"\n✅ No issues found that need automatic fixing")
        
        # Report remaining issues
        if issues_found:
            print(f"\n⚠️  {len(issues_found)} issue(s) require manual attention:")
            for issue in issues_found:
                print(f"   - {issue}")
            print("\n   To fix these:")
            print("   1. Go to Settings > LLM Providers in the UI")
            print("   2. Edit the provider and update the API key")
            print("   3. Click 'Test Connection' to verify")
            print("   4. Save the changes")
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total providers checked: {len(providers)}")
        print(f"Auto-fixed issues: {fixed_count}")
        print(f"Manual attention needed: {len(issues_found)}")
        
        if fixed_count > 0:
            print("\n⚠️  IMPORTANT: Restart the application for changes to take effect:")
            print("   docker-compose restart engine")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
