
import sys
import os
from sqlalchemy import text

# Add project root to path
sys.path.append(os.getcwd())

from app.database import SessionLocal, engine
from app.models_remediation import Runbook
from app.models_knowledge import DesignChunk
# Import all models to ensure ORM registry is populated
import app.models
import app.models_application
import app.models_application_knowledge
import app.models_scheduler
import app.models_troubleshooting
import app.models_itsm
import app.models_learning
import app.models_group
import app.models_revive

def check_runbook():
    db = SessionLocal()
    try:
        print("\n--- Searching for 'Apache' Runbooks ---")
        # Search for runbooks
        runbooks = db.query(Runbook).filter(Runbook.name.ilike("%Apache%")).all()
        
        if not runbooks:
            print("❌ No runbooks found matching 'Apache'")
            return
            
        for rb in runbooks:
            print(f"\nFound Runbook: {rb.name}")
            print(f"  ID: {rb.id}")
            print(f"  Enabled: {rb.enabled}")
            print(f"  Category: {rb.category}")
            print(f"  Steps: {len(rb.steps)}")
            
            # Check Knowledge/Vector Index
            print(f"  Checking Knowledge Index for Runbook ID {rb.id}...")
            # DesignChunks store entity_id as UUID in metadata or directly?
            # Usually RunbookKnowledgeService stores it in metadata={"runbook_id": str(id)}
            # Or strict linking? Let's check chunks with entity_type='runbook' and entity_id=rb.id?
            # The model might usage EntityMixin, let's try raw SQL for metadata check if strictly typed query is hard
            
            # Fetch all chunks and filter in python to avoid ORM complexity
            all_chunks = db.query(DesignChunk).all()
            chunks = []
            for c in all_chunks:
                # Use chunk_metadata as defined in model
                m = c.chunk_metadata or {}
                # Check for runbook_id in metadata
                if isinstance(m, dict) and str(m.get('runbook_id')) == str(rb.id):
                    chunks.append(c)
            
            if chunks:
                print(f"  FOUND {len(chunks)} knowledge chunks.")
                for c in chunks:
                    print(f"    - Chunk {c.id}: {c.content[:50]}...")
            else:
                print("  NOT FOUND: No knowledge chunks found (Runbook not indexed!)")
        
        if not runbooks:
            print("NO runbooks found matching 'Apache'")
            return

        print("\n--- Checking DesignDocument Table ---")
        from app.models_knowledge import DesignDocument
        
        # Search for DesignDocument with matching title or content
        docs = db.query(DesignDocument).filter(
            DesignDocument.doc_type == 'runbook',
            DesignDocument.title.ilike("%Apache%")
        ).all()
        
        if docs:
            print(f"  FOUND {len(docs)} DesignDocuments for Apache runbooks.")
            for d in docs:
                print(f"    - Doc ID: {d.id}")
                print(f"      Title: {d.title}")
                print(f"      Status: {d.status}")
        else:
            print("  NOT FOUND: No DesignDocument found for Apache runbooks.")
            print("  -> This explains why it is not visible in the Knowledge UI!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_runbook()
