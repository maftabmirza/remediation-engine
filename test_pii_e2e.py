"""
End-to-end PII and Secret detection test for chat security.
Tests both the PII API and the chat workflow to ensure sensitive data is protected.
"""
import asyncio
import httpx
import json

async def test_pii_e2e():
    base_url = 'http://localhost:8080'
    
    # 1. First test PII detection directly
    print('=' * 60)
    print('TEST 1: Direct PII Detection API')
    print('=' * 60)
    
    test_cases = [
        # PII cases - using patterns that Presidio recognizes
        {'text': 'Contact john.doe@example.com for help', 'expected': 'EMAIL'},
        {'text': 'SSN: 234-56-7890', 'expected': 'SSN'},  # Valid SSN pattern
        {'text': 'Call me at 555-123-4567', 'expected': 'PHONE'},
        {'text': 'Credit card: 4111-1111-1111-1111', 'expected': 'CREDIT'},
        
        # Secret cases - using patterns detect-secrets recognizes
        {'text': 'My AWS key is AKIAIOSFODNN7EXAMPLE', 'expected': 'AWS'},
        {'text': 'Token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'expected': 'GitHub'},  # 40 chars
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        passed = 0
        failed = 0
        
        for case in test_cases:
            response = await client.post(
                f'{base_url}/api/v1/pii/detect',
                json={
                    'text': case['text'],
                    'source_type': 'test',
                    'engines': ['presidio', 'detect_secrets']
                }
            )
            data = response.json()
            detections = data.get('detections', [])
            detected_types = [d.get('entity_type', '') for d in detections]
            
            found = any(case['expected'].lower() in str(d).lower() for d in detections)
            status = '✅ PASS' if found else '❌ FAIL'
            if found:
                passed += 1
            else:
                failed += 1
            print(f'{status} Input: "{case["text"][:40]}..."')
            print(f'       Expected: {case["expected"]} | Found: {detected_types}')
        
        print(f'\nDetection Results: {passed}/{passed+failed} passed')
        
        # 2. Test redaction
        print()
        print('=' * 60)
        print('TEST 2: PII Redaction')
        print('=' * 60)
        
        test_text = '''Hello, my name is John Smith. 
My email is john.smith@company.com and my SSN is 234-56-7890.
The AWS access key is AKIAIOSFODNN7EXAMPLE.
Credit card: 4111111111111111'''
        
        response = await client.post(
            f'{base_url}/api/v1/pii/redact',
            json={
                'text': test_text,
                'redaction_type': 'tag'
            }
        )
        data = response.json()
        print(f'Original ({len(test_text)} chars):')
        print(test_text)
        print()
        print(f'Redacted ({data.get("redactions_applied", 0)} items):')
        print(data.get('redacted_text', 'ERROR'))
        
        # Verify sensitive data is NOT in redacted text
        redacted = data.get('redacted_text', '')
        leaks = []
        sensitive_items = [
            'john.smith@company.com',
            '234-56-7890',
            'AKIAIOSFODNN7EXAMPLE',
            '4111111111111111',
        ]
        for item in sensitive_items:
            if item in redacted:
                leaks.append(item)
        
        print()
        if leaks:
            print(f'❌ SECURITY ISSUE: Found {len(leaks)} unredacted sensitive items:')
            for leak in leaks:
                print(f'   - {leak}')
        else:
            print('✅ All sensitive data properly redacted')

if __name__ == '__main__':
    asyncio.run(test_pii_e2e())
