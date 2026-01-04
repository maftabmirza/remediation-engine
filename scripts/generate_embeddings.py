"""
Script to generate embeddings for existing chunks that don't have them.
Run inside the container: python scripts/generate_embeddings.py
"""
import os
import sys
sys.path.insert(0, '/app')

# Import database and models the same way main.py does
from app.database import SessionLocal, engine, Base

# Import all models to register them
from app import models
from app import models_agent
from app import models_ai_helper
from app import models_application
from app import models_chat
from app import models_dashboards
from app import models_group
from app import models_itsm
from app import models_knowledge
from app import models_learning
from app import models_remediation
from app import models_runbook_acl
from app import models_scheduler
from app import models_troubleshooting

from app.models_knowledge import DesignChunk
from app.services.embedding_service import EmbeddingService

def main():
    db = SessionLocal()
    embedding_service = EmbeddingService()
    
    if not embedding_service.is_configured():
        print("❌ Embedding service not configured (missing OpenAI API key)")
        db.close()
        return
    
    print("✓ Embedding service is configured")
    
    # Get chunks without embeddings
    chunks = db.query(DesignChunk).filter(DesignChunk.embedding == None).all()
    print(f"Found {len(chunks)} chunks without embeddings")
    
    if not chunks:
        print("✅ All chunks already have embeddings!")
        db.close()
        return
    
    # Process in batches of 100
    batch_size = 100
    total_embedded = 0
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        texts = [chunk.content for chunk in batch]
        
        print(f"Processing batch {i//batch_size + 1} ({len(batch)} chunks)...")
        
        try:
            embeddings = embedding_service.generate_embeddings_batch(texts)
            
            for chunk, embedding in zip(batch, embeddings):
                if embedding:
                    chunk.embedding = embedding
                    total_embedded += 1
            
            db.commit()
            print(f"  ✓ Embedded {total_embedded} chunks so far")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            db.rollback()
    
    db.close()
    print(f"\n✅ Done! Generated {total_embedded} embeddings")

if __name__ == "__main__":
    main()
