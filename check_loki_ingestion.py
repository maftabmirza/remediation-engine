import asyncio
import httpx
import json

LOKI_URL = "http://localhost:3100"

async def main():
    print(f"--- Qurying Loki at {LOKI_URL} ---")
    
    # Query for our injected error
    # Log: [error] ... Connection refused ...
    query = '{job="varlogs"} |= "Connection refused"'
    
    params = {
        "query": query,
        "limit": 10
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{LOKI_URL}/loki/api/v1/query_range", params=params)
            if response.status_code == 200:
                data = response.json()
                print("Loki Response Status: OK")
                results = data.get('data', {}).get('result', [])
                print(f"Found {len(results)} streams matching query.")
                
                count = 0
                for stream in results:
                    for value in stream.get('values', []):
                        # timestamp, line
                        print(f"LOG: {value[1]}")
                        count += 1
                
                if count > 0:
                    print(f"\nSUCCESS: Found {count} matching log entries.")
                else:
                    print("\nFAILURE: No matching logs found yet.")
            else:
                print(f"Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Connection Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
