
import time
import asyncio
from app.database import SessionLocal
from app.services.embedding_service import EmbeddingService
from app.services.similarity_service import SimilarityService
# Import all models to ensure Registry is populated and relationships work
import app.models
import app.models_chat 
import app.models_troubleshooting
from app.models import Alert
import uuid

async def test_performance():
    db = SessionLocal()
    print("--- Performance Test Started ---")
    
    # 1. Embedding Generation
    # Checking class name - assuming EmbeddingService based on file name
    try:
        vector_service = EmbeddingService()
        test_text = "Database connection timeout occurred while connecting to postgres. CPU usage is high."
        
        start_time = time.time()
        embedding = await vector_service.generate_embedding(test_text)
        end_time = time.time()
        
        gen_time = (end_time - start_time) * 1000
        print(f"Embedding Generation (Ollama/LLM): {gen_time:.2f} ms")
        
        if not embedding:
            print("FAILED: No embedding generated")
            return
    except Exception as e:
        print(f"Embedding check failed: {e}")

    # 2. Similarity Search
    # Create a dummy alert to search for
    alert = db.query(Alert).first()
    if not alert:
        print("SKIP: No alerts in DB to test search")
        db.close()
        return
        
    sim_service = SimilarityService(db)
    
    start_time = time.time()
    results = sim_service.find_similar_alerts(alert.id, limit=5)
    end_time = time.time()
    
    search_time = (end_time - start_time) * 1000
    print(f"Similarity Search (pgvector): {search_time:.2f} ms")
    print(f"Found {results.total_found} similar alerts")

    db.close()
    print("--- Performance Test Finished ---")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_performance())
