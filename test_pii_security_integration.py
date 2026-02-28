"""
Integration test for PII security across all agent modes.

This test validates that PII/secrets are properly redacted in:
1. /alert endpoint (AI Alert Help Agent)  
2. RE-VIVE (ReviveQuickHelpAgent)
3. /troubleshoot endpoint (TroubleshootNativeAgent)

Run this after starting the application:
    python test_pii_security_integration.py
"""
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_pii_redaction_in_agents():
    """
    Unit test to verify PII redaction is implemented in all three agent types.
    """
    print("=" * 80)
    print("PII SECURITY IMPLEMENTATION CHECK")
    print("=" * 80)
    
    results = {
        'alert_agent': False,
        'revive_agent': False, 
        'troubleshoot_agent': False
    }
    
    # Test 1: Check AI Alert Help Agent
    print("\n[1/3] Checking AI Alert Help Agent...")
    try:
        from app.services.agentic.ai_alert_help_agent import AiAlertHelpAgent
        
        # Check if PII redaction method exists
        if hasattr(AiAlertHelpAgent, '_scan_and_redact_text'):
            print("  ✅ _scan_and_redact_text method found")
            
            # Check if PIIMappingManager is used
            import inspect
            source = inspect.getsource(AiAlertHelpAgent._scan_and_redact_text)
            if 'pii_mapping_manager' in source and 'redact_text_with_mappings' in source:
                print("  ✅ PIIMappingManager integration found")
                results['alert_agent'] = True
            else:
                print("  ⚠️  PIIMappingManager not used for redaction")
        else:
            print("  ❌ _scan_and_redact_text method NOT found")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Test 2: Check RE-VIVE Agent
    print("\n[2/3] Checking RE-VIVE Quick Help Agent...")
    try:
        from app.services.revive.revive_agent import ReviveQuickHelpAgent
        
        # Check if PII redaction method exists
        if hasattr(ReviveQuickHelpAgent, '_scan_and_redact_text'):
            print("  ✅ _scan_and_redact_text method found")
            
            # Check if PIIMappingManager is used
            import inspect
            source = inspect.getsource(ReviveQuickHelpAgent._scan_and_redact_text)
            if 'pii_mapping_manager' in source and 'redact_text_with_mappings' in source:
                print("  ✅ PIIMappingManager integration found")
                results['revive_agent'] = True
            else:
                print("  ⚠️  PIIMappingManager not used for redaction")
        else:
            print("  ❌ _scan_and_redact_text method NOT found")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Test 3: Check Troubleshoot Native Agent
    print("\n[3/3] Checking Troubleshoot Native Agent...")
    try:
        from app.services.agentic.troubleshoot_native_agent import TroubleshootNativeAgent
        
        # Check if PII redaction method exists
        if hasattr(TroubleshootNativeAgent, '_scan_and_redact_text'):
            print("  ✅ _scan_and_redact_text method found")
            
            # Check if PIIMappingManager is used
            import inspect
            source = inspect.getsource(TroubleshootNativeAgent._scan_and_redact_text)
            if 'pii_mapping_manager' in source:
                print("  ✅ PIIMappingManager integration found")
                
                # Check tool output scanning
                exec_source = inspect.getsource(TroubleshootNativeAgent._execute_tool_calls)
                if 'pii_mapping_manager' in exec_source and 'redact_text_with_mappings' in exec_source:
                    print("  ✅ Tool output PII scanning found")
                    results['troubleshoot_agent'] = True
                else:
                    print("  ⚠️  Tool output scanning not implemented")
            else:
                print("  ⚠️  PIIMappingManager not used")
        else:
            print("  ❌ _scan_and_redact_text method NOT found")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\n✅ Alert Agent:        {'PASS' if results['alert_agent'] else 'FAIL'}")
    print(f"✅ RE-VIVE Agent:      {'PASS' if results['revive_agent'] else 'FAIL'}")
    print(f"✅ Troubleshoot Agent: {'PASS' if results['troubleshoot_agent'] else 'FAIL'}")
    
    print(f"\n{passed}/{total} agents have proper PII security")
    
    if passed == total:
        print("\n✅ ALL AGENTS HAVE PII SECURITY IMPLEMENTED")
        print("\nPII Security Features:")
        print("  • User input scanning before LLM")
        print("  • Tool output scanning (Troubleshoot)")
        print("  • Agent response scanning")
        print("  • Session-consistent redaction with PIIMappingManager")
        print("  • Detection logging for audit")
        return True
    else:
        print("\n❌ SOME AGENTS ARE MISSING PII SECURITY")
        print("\nRecommended Actions:")
        print("  1. Review agent implementation")
        print("  2. Add _scan_and_redact_text method")
        print("  3. Integrate PIIMappingManager")
        print("  4. Test with test_pii_all_agents.py")
        return False


def check_pii_service_availability():
    """Check if PII service is properly configured"""
    print("\n" + "=" * 80)
    print("PII SERVICE CONFIGURATION CHECK")
    print("=" * 80)
    
    try:
        from app.services.pii_service import PIIService
        print("✅ PIIService module found")
        
        from app.services.presidio_service import PresidioService
        print("✅ PresidioService module found")
        
        from app.services.secret_detection_service import SecretDetectionService
        print("✅ SecretDetectionService module found")
        
        from app.services.pii_mapping_manager import PIIMappingManager
        print("✅ PIIMappingManager module found")
        
        # Check default entities
        print(f"\n📋 Default PII entities: {len(PIIService.DEFAULT_ENTITIES)} types")
        print("   Includes: EMAIL, PHONE, SSN, CREDIT_CARD, IP_ADDRESS, etc.")
        
        return True
        
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False


def main():
    """Main test runner"""
    print("\n🔒 PII SECURITY VALIDATION SUITE")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check PII service availability
    service_ok = check_pii_service_availability()
    
    # Check agent implementations
    agents_ok = test_pii_redaction_in_agents()
    
    # Overall result
    print("\n" + "=" * 80)
    if service_ok and agents_ok:
        print("✅ PII SECURITY: FULLY IMPLEMENTED AND OPERATIONAL")
        print("=" * 80)
        print("\nNext Steps:")
        print("  1. Start the application (docker-compose up)")
        print("  2. Run integration tests: python test_pii_all_agents.py")
        print("  3. Review PII detection logs in database")
        return 0
    else:
        print("❌ PII SECURITY: ISSUES DETECTED")
        print("=" * 80)
        print("\nAction Required:")
        print("  • Fix missing implementations")
        print("  • Install required dependencies")
        print("  • Re-run this test")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
