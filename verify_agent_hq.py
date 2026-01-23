import requests
import sys

# Configuration
BASE_URL = "http://localhost:8080"
# Use the session ID that was failing in the logs (user ID)
SESSION_ID = "b2918297-5832-4490-ad45-bb8f4e071e9c" 

def test_agent_hq():
    print(f"Testing Agent HQ API with Session ID: {SESSION_ID}")
    url = f"{BASE_URL}/api/agents/hq/{SESSION_ID}"
    
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("Response JSON:")
            print(response.json())
            print("✅ API Test Passed")
        else:
            print(f"❌ API Test Failed: {response.text}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Connection Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_agent_hq()
