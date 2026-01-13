import urllib.request
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_search_api():
    url = "http://localhost:8080/api/knowledge/search"
    payload = {
        "query": "grafana",
        "limit": 5
    }
    
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            logger.info(f"API Request Status: {status}")
            
            if status == 200:
                body = response.read().decode('utf-8')
                data = json.loads(body)
                results = data.get('results', [])
                total = data.get('total_found', 0)
                
                logger.info(f"Total Found: {total}")
                logger.info(f"Results Returned: {len(results)}")
                
                if len(results) > 0:
                    logger.info("Top result:")
                    logger.info(f" - Title: {results[0].get('source_title')}")
                    logger.info(f" - Score: {results[0].get('similarity')}")
                    logger.info(f" - Content Snippet: {results[0].get('content')[:100]}...")
                else:
                    logger.warning("No results found for query 'grafana'")
            else:
                logger.error(f"API returned non-200 status: {status}")
                
    except Exception as e:
        logger.error(f"API Test Failed: {e}")

if __name__ == "__main__":
    test_search_api()
