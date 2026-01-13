import sys
import logging
import json
from app.database import SessionLocal
from app.services.knowledge_search_service import KnowledgeSearchService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verify_search_service():
    db = SessionLocal()
    try:
        service = KnowledgeSearchService(db)
        query = "grafana"
        
        logger.info(f"Testing search for query: '{query}'")
        
        # Test vector search (will fallback to text if not configured)
        results = service.search_similar(query, limit=5)
        
        logger.info(f"Total Results: {len(results)}")
        
        if len(results) > 0:
            logger.info("Top Result:")
            top = results[0]
            logger.info(f" - Title: {top.get('source_title')}")
            logger.info(f" - Type: {top.get('source_type')}")
            logger.info(f" - Similarity: {top.get('similarity')}")
            logger.info(f" - Content Snippet: {top.get('content')[:100]}...")
        else:
            logger.warning("No results found.")
            
    except Exception as e:
        logger.error(f"Search Service Verification Failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_search_service()
