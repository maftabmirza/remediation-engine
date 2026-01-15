import sys
import os
import logging
from sqlalchemy import func
from app.database import SessionLocal
from app.models_knowledge import DesignDocument, DesignChunk

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verify_knowledge():
    db = SessionLocal()
    try:
        # 1. Count Documents
        doc_count = db.query(DesignDocument).count()
        logger.info(f"Total Documents: {doc_count}")

        if doc_count == 0:
            logger.warning("No documents found! Git sync might have failed to save to DB.")
            return

        # 2. Key Document Samples
        docs = db.query(DesignDocument).limit(5).all()
        logger.info("Sample Documents:")
        for doc in docs:
            logger.info(f" - {doc.title} ({doc.doc_type}, {doc.source_type}) - ID: {doc.id}")

        # 3. Count Chunks
        chunk_count = db.query(DesignChunk).count()
        logger.info(f"Total Chunks: {chunk_count}")

        if chunk_count == 0:
            logger.warning("No chunks found! Auto-chunking might be failing.")
        else:
            avg_chunks = chunk_count / doc_count
            logger.info(f"Average chunks per document: {avg_chunks:.2f}")

        # 4. Check Embeddings
        # Count chunks with non-null embeddings
        embedded_count = db.query(DesignChunk).filter(DesignChunk.embedding != None).count()
        logger.info(f"Chunks with Embeddings: {embedded_count}")

        if embedded_count == 0:
            logger.error("CRITICAL: No embeddings generated! Search will not work.")
        elif embedded_count < chunk_count:
            logger.warning(f"Partial embeddings: {chunk_count - embedded_count} chunks are missing embeddings.")
        else:
            logger.info("SUCCESS: All chunks have embeddings.")

    except Exception as e:
        logger.error(f"Verification failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_knowledge()
