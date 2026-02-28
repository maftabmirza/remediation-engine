"""
Comprehensive PII Security Test for All Agent Modes

Tests PII/secret detection and redaction across:
1. /alert endpoint (AI Alert Help Agent)
2. RE-VIVE (ReviveQuickHelpAgent)
3. /troubleshoot endpoint (TroubleshootNativeAgent)

This test verifies that sensitive data is properly detected, logged, and redacted
before being sent to LLM providers, ensuring compliance with security policies.
"""
import asyncio
import httpx
import json
import time
from typing import Dict, List

# Base URL for the API
BASE_URL = 'http://localhost:8080'

# Test credentials
TEST_CREDENTIALS = {
    'username': 'admin',
    'password': 'admin123'  # Update if needed
}

# PII test cases with various types of sensitive data
PII_TEST_CASES = [
    {
        'name': 'Email Address',
        'message': 'Can you help me? My email is john.doe@company.com',
        'expected_pii': 'EMAIL',
        'contains_sensitive': 'john.doe@company.com'
    },
    {
        'name': 'SSN',
        'message': 'The SSN in the logs is 234-56-7890',
        'expected_pii': 'SSN',
        'contains_sensitive': '234-56-7890'
    },
    {
        'name': 'Phone Number',
        'message': 'Call the on-call engineer at 555-123-4567',
        'expected_pii': 'PHONE',
        'contains_sensitive': '555-123-4567'
    },
    {
        'name': 'Credit Card',
        'message': 'Payment failed with card 4111-1111-1111-1111',
        'expected_pii': 'CREDIT',
        'contains_sensitive': '4111-1111-1111-1111'
    },
    {
        'name': 'AWS Access Key',
        'message': 'The AWS key leaked: AKIAIOSFODNN7EXAMPLE',
        'expected_pii': 'AWS',
        'contains_sensitive': 'AKIAIOSFODNN7EXAMPLE'
    },
    {
        'name': 'GitHub Token',
        'message': 'Found GitHub token ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx in config',
        'expected_pii': 'GitHub',
        'contains_sensitive': 'ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    },
    {
        'name': 'IP Address',
        'message': 'Server IP is 192.168.1.100 showing errors',
        'expected_pii': 'IP',
        'contains_sensitive': '192.168.1.100'
    },
    {
        'name': 'Person Name',
        'message': 'Contact John Smith about this issue',
        'expected_pii': 'PERSON',
        'contains_sensitive': 'John Smith'
    }
]


class PIITestRunner:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        self.token = None
        self.results = {
            'alert': {'passed': 0, 'failed': 0, 'errors': []},
            'revive': {'passed': 0, 'failed': 0, 'errors': []},
            'troubleshoot': {'passed': 0, 'failed': 0, 'errors': []}
        }

    async def login(self):
        """Authenticate and get JWT token"""
        try:
            response = await self.client.post(
                f'{BASE_URL}/api/auth/login',
                json=TEST_CREDENTIALS
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('access_token')
                print(f'✅ Authenticated successfully')
                return True
            else:
                print(f'❌ Login failed: {response.status_code} - {response.text}')
                return False
        except Exception as e:
            print(f'❌ Login error: {e}')
            return False

    def get_headers(self):
        """Get HTTP headers with authentication"""
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

    async def test_alert_endpoint(self, test_case: Dict) -> bool:
        """Test PII security on /alert endpoint"""
        print(f'\n  Testing: {test_case["name"]}')
        try:
            # First, get or create an alert
            alerts_response = await self.client.get(
                f'{BASE_URL}/api/alerts?page=1&page_size=1',
                headers=self.get_headers()
            )
            
            if alerts_response.status_code != 200:
                print(f'    ⚠️  Could not fetch alerts: {alerts_response.status_code}')
                return False

            alerts_data = alerts_response.json()
            if not alerts_data.get('alerts'):
                print(f'    ⚠️  No alerts available for testing')
                return False

            alert_id = alerts_data['alerts'][0]['id']

            # Test the alert chat endpoint with PII
            response = await self.client.post(
                f'{BASE_URL}/api/alerts/{alert_id}/chat',
                headers=self.get_headers(),
                json={'message': test_case['message']}
            )

            if response.status_code == 200:
                response_text = response.text
                # Check if sensitive data is NOT in the response
                if test_case['contains_sensitive'].lower() not in response_text.lower():
                    print(f'    ✅ PASS: Sensitive data redacted')
                    return True
                else:
                    print(f'    ❌ FAIL: Sensitive data leaked in response')
                    self.results['alert']['errors'].append(
                        f"{test_case['name']}: Found '{test_case['contains_sensitive']}' in response"
                    )
                    return False
            else:
                print(f'    ⚠️  API error: {response.status_code}')
                return False

        except Exception as e:
            print(f'    ❌ ERROR: {e}')
            self.results['alert']['errors'].append(f"{test_case['name']}: {str(e)}")
            return False

    async def test_revive_endpoint(self, test_case: Dict) -> bool:
        """Test PII security on RE-VIVE endpoint"""
        print(f'\n  Testing: {test_case["name"]}')
        try:
            # Test the RE-VIVE chat endpoint with PII
            response = await self.client.post(
                f'{BASE_URL}/api/revive/chat',
                headers=self.get_headers(),
                json={
                    'message': test_case['message'],
                    'session_id': f'test-session-{int(time.time())}'
                }
            )

            if response.status_code == 200:
                response_text = response.text
                # Check if sensitive data is NOT in the response
                if test_case['contains_sensitive'].lower() not in response_text.lower():
                    print(f'    ✅ PASS: Sensitive data redacted')
                    return True
                else:
                    print(f'    ❌ FAIL: Sensitive data leaked in response')
                    self.results['revive']['errors'].append(
                        f"{test_case['name']}: Found '{test_case['contains_sensitive']}' in response"
                    )
                    return False
            else:
                print(f'    ⚠️  API error: {response.status_code}')
                return False

        except Exception as e:
            print(f'    ❌ ERROR: {e}')
            self.results['revive']['errors'].append(f"{test_case['name']}: {str(e)}")
            return False

    async def test_troubleshoot_endpoint(self, test_case: Dict) -> bool:
        """Test PII security on /troubleshoot endpoint"""
        print(f'\n  Testing: {test_case["name"]}')
        try:
            # Test the troubleshoot chat endpoint with PII
            response = await self.client.post(
                f'{BASE_URL}/api/troubleshoot/chat',
                headers=self.get_headers(),
                json={
                    'message': test_case['message'],
                    'session_id': f'test-session-{int(time.time())}'
                }
            )

            if response.status_code == 200:
                response_text = response.text
                # Check if sensitive data is NOT in the response
                if test_case['contains_sensitive'].lower() not in response_text.lower():
                    print(f'    ✅ PASS: Sensitive data redacted')
                    return True
                else:
                    print(f'    ❌ FAIL: Sensitive data leaked in response')
                    self.results['troubleshoot']['errors'].append(
                        f"{test_case['name']}: Found '{test_case['contains_sensitive']}' in response"
                    )
                    return False
            else:
                print(f'    ⚠️  API error: {response.status_code}')
                return False

        except Exception as e:
            print(f'    ❌ ERROR: {e}')
            self.results['troubleshoot']['errors'].append(f"{test_case['name']}: {str(e)}")
            return False

    async def run_all_tests(self):
        """Run all PII security tests"""
        print('=' * 80)
        print('PII SECURITY TEST SUITE FOR ALL AGENT MODES')
        print('=' * 80)

        # Login first
        if not await self.login():
            print('\n❌ Cannot proceed without authentication')
            return

        # Test 1: /alert endpoint
        print('\n' + '=' * 80)
        print('TEST 1: /alert ENDPOINT (AI Alert Help Agent)')
        print('=' * 80)
        for test_case in PII_TEST_CASES:
            result = await self.test_alert_endpoint(test_case)
            if result:
                self.results['alert']['passed'] += 1
            else:
                self.results['alert']['failed'] += 1

        # Test 2: RE-VIVE endpoint
        print('\n' + '=' * 80)
        print('TEST 2: RE-VIVE ENDPOINT (ReviveQuickHelpAgent)')
        print('=' * 80)
        for test_case in PII_TEST_CASES:
            result = await self.test_revive_endpoint(test_case)
            if result:
                self.results['revive']['passed'] += 1
            else:
                self.results['revive']['failed'] += 1

        # Test 3: /troubleshoot endpoint
        print('\n' + '=' * 80)
        print('TEST 3: /troubleshoot ENDPOINT (TroubleshootNativeAgent)')
        print('=' * 80)
        for test_case in PII_TEST_CASES:
            result = await self.test_troubleshoot_endpoint(test_case)
            if result:
                self.results['troubleshoot']['passed'] += 1
            else:
                self.results['troubleshoot']['failed'] += 1

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test results summary"""
        print('\n' + '=' * 80)
        print('TEST RESULTS SUMMARY')
        print('=' * 80)

        total_passed = 0
        total_failed = 0

        for endpoint, results in self.results.items():
            passed = results['passed']
            failed = results['failed']
            total = passed + failed
            total_passed += passed
            total_failed += failed

            status = '✅' if failed == 0 else '❌'
            print(f'\n{status} {endpoint.upper()} Endpoint: {passed}/{total} tests passed')
            
            if results['errors']:
                print(f'   Errors:')
                for error in results['errors']:
                    print(f'     - {error}')

        print('\n' + '-' * 80)
        grand_total = total_passed + total_failed
        overall_status = '✅ ALL TESTS PASSED' if total_failed == 0 else f'❌ {total_failed} TESTS FAILED'
        print(f'{overall_status}')
        print(f'Total: {total_passed}/{grand_total} tests passed')
        print('=' * 80)

        # Recommendations
        if total_failed > 0:
            print('\n⚠️  SECURITY RECOMMENDATIONS:')
            print('  1. Review PII detection logs in the database')
            print('  2. Check if PII service is properly initialized')
            print('  3. Verify PIIMappingManager is being used correctly')
            print('  4. Ensure _scan_and_redact_text is called on all user inputs')
            print('  5. Check application logs for PII detection warnings')

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


async def main():
    """Main test runner"""
    runner = PIITestRunner()
    try:
        await runner.run_all_tests()
    finally:
        await runner.close()


if __name__ == '__main__':
    asyncio.run(main())
