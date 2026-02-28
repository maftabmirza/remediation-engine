"""
Test script to verify PII whitelist functionality is working correctly.

This script tests:
1. Reporting an email as false positive
2. Verifying it's added to whitelist
3. Running detection again and confirming it's no longer detected
"""
import asyncio
import sys
from uuid import uuid4

# Add app to path
sys.path.insert(0, '.')

from app.database import async_engine, AsyncSessionLocal
from app.services.presidio_service import PresidioService
from app.services.secret_detection_service import SecretDetectionService
from app.services.pii_service import PIIService
from app.services.pii_whitelist_service import PIIWhitelistService
from app.schemas.pii_schemas import FalsePositiveFeedbackRequest


async def test_whitelist_workflow():
    """Test the complete whitelist workflow."""
    print("=" * 80)
    print("PII WHITELIST FUNCTIONALITY TEST")
    print("=" * 80)
    
    # Test email that will be reported as false positive
    test_email = "aftab@gmail.com"
    test_text = f"Hello, I am Aftab and email is {test_email}"
    
    async with AsyncSessionLocal() as db:
        try:
            # Initialize services
            print("\n📦 Initializing services...")
            presidio = PresidioService()
            secrets = SecretDetectionService()
            whitelist_service = PIIWhitelistService(db)
            pii_service = PIIService(db, presidio, secrets, whitelist_service=whitelist_service)
            
            # Step 1: Detect PII in text (should detect email)
            print(f"\n🔍 Step 1: Running initial PII detection on: '{test_text}'")
            result1 = await pii_service.detect(
                text=test_text,
                source_type="test",
                engines=['presidio']
            )
            
            print(f"   Found {len(result1.detections)} detections:")
            for det in result1.detections:
                print(f"   - {det.entity_type}: '{det.value}' (confidence: {det.confidence:.2f})")
            
            # Verify email was detected
            email_detected = any(det.value == test_email for det in result1.detections)
            if not email_detected:
                print(f"\n❌ FAIL: Email '{test_email}' was not detected in initial scan")
                return False
            
            print(f"\n✅ Email '{test_email}' was detected as expected")
            
            # Step 2: Report email as false positive
            print(f"\n📝 Step 2: Reporting '{test_email}' as false positive...")
            
            # Create mock user ID
            mock_user_id = uuid4()
            
            feedback_request = FalsePositiveFeedbackRequest(
                detected_text=test_email,
                detected_entity_type="EMAIL_ADDRESS",
                detection_engine="presidio",
                original_confidence=0.95,
                whitelist_scope="organization",
                user_comment="This is our company domain, not PII"
            )
            
            feedback_response = await whitelist_service.submit_feedback(
                request=feedback_request,
                user_id=mock_user_id
            )
            
            print(f"   Feedback submitted: {feedback_response.message}")
            print(f"   Whitelisted: {feedback_response.whitelisted}")
            print(f"   Review Status: {feedback_response.review_status}")
            
            # Step 3: Clear cache to force reload
            print("\n🔄 Step 3: Clearing whitelist cache to force reload...")
            whitelist_service.clear_cache()
            
            # Step 4: Run detection again (should NOT detect the email)
            print(f"\n🔍 Step 4: Running PII detection again on same text...")
            result2 = await pii_service.detect(
                text=test_text,
                source_type="test",
                engines=['presidio']
            )
            
            print(f"   Found {len(result2.detections)} detections:")
            for det in result2.detections:
                print(f"   - {det.entity_type}: '{det.value}' (confidence: {det.confidence:.2f})")
            
            # Verify email was NOT detected this time
            email_detected_again = any(det.value == test_email for det in result2.detections)
            
            if email_detected_again:
                print(f"\n❌ FAIL: Email '{test_email}' was still detected after whitelisting!")
                print("   The whitelist is not working correctly.")
                return False
            
            print(f"\n✅ SUCCESS: Email '{test_email}' is no longer detected!")
            print("   The whitelist is working correctly.")
            
            # Step 5: Verify whitelist contains the email
            print(f"\n📋 Step 5: Verifying whitelist contents...")
            is_whitelisted = await whitelist_service.is_whitelisted(
                text=test_email,
                entity_type="EMAIL_ADDRESS",
                scope="organization"
            )
            
            if is_whitelisted:
                print(f"   ✅ Confirmed: '{test_email}' is in the whitelist")
            else:
                print(f"   ❌ FAIL: '{test_email}' is NOT in the whitelist!")
                return False
            
            # Get full whitelist
            whitelist = await whitelist_service.get_whitelist(
                scope="organization",
                active_only=True
            )
            
            print(f"\n📊 Whitelist Statistics:")
            print(f"   Total entries: {whitelist.total}")
            print(f"   Entries:")
            for item in whitelist.items:
                print(f"   - {item.entity_type}: '{item.text}' (scope: {item.scope})")
            
            print("\n" + "=" * 80)
            print("✅ ALL TESTS PASSED!")
            print("=" * 80)
            return True
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Main entry point."""
    try:
        success = await test_whitelist_workflow()
        sys.exit(0 if success else 1)
    finally:
        # Clean up database engine
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
