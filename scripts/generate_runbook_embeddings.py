import sys
import os
import logging
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
# Import ALL models to ensure SQLAlchemy registry is fully populated
try:
    from app.models import *
    from app.models_agent import *
    from app.models_ai_helper import *
    from app.models_application import *
    from app.models_chat import *
    from app.models_dashboards import *
    from app.models_group import *
    from app.models_itsm import *
    from app.models_knowledge import *
    from app.models_learning import *
    from app.models_remediation import *
    from app.models_runbook_acl import *
    from app.models_scheduler import *
    from app.models_troubleshooting import *
except ImportError as e:
    logging.warning(f"Could not import some models: {e}")

from app.services.embedding_service import EmbeddingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_embeddings():
    """Generate and update embeddings for all runbooks."""
    logger.info("Starting runbook embedding generation...")
    
    db = SessionLocal()
    embedding_service = EmbeddingService()
    
    if not embedding_service.is_configured():
        logger.error("Embedding service is not configured (missing API key). Please set OPENAI_API_KEY environment variable.")
        return

    try:
        runbooks = db.query(Runbook).all()
        logger.info(f"Found {len(runbooks)} runbooks")
        
        updated_count = 0
        skipped_count = 0
        error_count = 0

        for runbook in runbooks:
            try:
                # Construct rich text representation for embedding
                parts = [f"Title: {runbook.name}"]
                
                if runbook.description:
                    parts.append(f"Description: {runbook.description}")
                
                if runbook.tags:
                    # Handle tags if they are list or string
                    tags_str = runbook.tags if isinstance(runbook.tags, str) else ", ".join(runbook.tags)
                    parts.append(f"Tags: {tags_str}")
                
                if runbook.steps:
                    # Summarize steps from relationship
                    steps_list = []
                    for step in runbook.steps:
                        steps_list.append(f"{step.step_order}. {step.name} ({step.step_type})")
                    
                    steps_desc = "; ".join(steps_list)
                    # Limit step content length
                    if len(steps_desc) > 2000:
                        steps_desc = steps_desc[:2000] + "..."
                    parts.append(f"Steps: {steps_desc}")

                text_to_embed = "\n".join(parts)
                
                logger.info(f"Generating embedding for runbook: {runbook.name} (ID: {runbook.id})")
                embedding = embedding_service.generate_embedding(text_to_embed)
                
                if embedding:
                    runbook.embedding = embedding
                    updated_count += 1
                else:
                    logger.warning(f"Failed to generate embedding for {runbook.id} - API returned None")
                    error_count += 1
            
            except Exception as e:
                logger.error(f"Error processing runbook {runbook.id}: {e}")
                error_count += 1

        db.commit()
        logger.info(f"Completed runbook embedding generation.")
        logger.info(f"Updated: {updated_count}")
        logger.info(f"Errors: {error_count}")
        
    except Exception as e:
        logger.error(f"Critical error during embedding generation: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    generate_embeddings()
