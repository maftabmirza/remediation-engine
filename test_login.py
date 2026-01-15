
import sys
import json
import urllib.request
import urllib.error

def test_login():
    url = "http://localhost:8080/api/auth/login"
    data = json.dumps({"username": "admin", "password": "admin"}).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    
    req = urllib.request.Request(url, data=data, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            body = response.read().decode('utf-8')
            print(f"Status: {status}")
            print(f"Response: {body}")
            
            if status == 200:
                print("LOGIN SUCCESSFUL")
            else:
                print("LOGIN FAILED")
                
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        print(f"Reason: {e.reason}")
        print(f"Body: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_login()
