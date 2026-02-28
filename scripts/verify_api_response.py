import requests
import json
import sys

def verify_api():
    url = "http://localhost:8080/api/incidents?time_range=30d&page=1&page_size=25"
    print(f"Requesting {url}...")
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("Response Type:", type(data))
            if isinstance(data, list):
                print(f"Response List Length: {len(data)}")
                if len(data) > 0:
                    print("First item sample:")
                    print(json.dumps(data[0], indent=2))
            else:
                print("Response is NOT a list!")
                print("Response Keys:", data.keys() if isinstance(data, dict) else "N/A")
                print(json.dumps(data, indent=2))
        else:
            print("Error Response:")
            print(response.text)
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    verify_api()
