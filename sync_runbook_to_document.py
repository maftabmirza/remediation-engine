
import sys
import os
import uuid
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.models_remediation import Runbook
from app.models_knowledge import DesignDocument

# Import all models
import app.models
import app.models_application
import app.models_scheduler
import app.models_troubleshooting
import app.models_itsm
import app.models_learning
import app.models_group
import app.models_revive
import app.models_application_knowledge

def create_runbook_document():
    db = SessionLocal()
    try:
        print("\n--- Syncing Runbook to DesignDocument ---")
        
        # 1. Find the Runbook
        runbook = db.query(Runbook).filter(Runbook.name.ilike("%Apache%")).first()
        if not runbook:
            print("❌ Runbook 'Apache' not found!")
            return

        print(f"Found Runbook: {runbook.name} ({runbook.id})")

        # 2. Check if Document already exists (by title or slug)
        existing_doc = db.query(DesignDocument).filter(
            DesignDocument.doc_type == 'runbook',
            DesignDocument.title == runbook.name
        ).first()

        if existing_doc:
            print(f"⚠️ DesignDocument already exists: {existing_doc.title} ({existing_doc.id})")
            return

        # 3. Create DesignDocument content (Markdown representation)
        content_lines = [
            f"# {runbook.name}",
            f"\n**Description**: {runbook.description}",
            f"\n**Tags**: {', '.join(runbook.tags or [])}",
            "\n## Steps"
        ]
        
        for step in sorted(runbook.steps, key=lambda s: s.step_order):
            content_lines.append(f"\n### {step.step_order}. {step.name}")
            content_lines.append(step.description or "")
            if step.command_linux:
                content_lines.append(f"**Linux**:\n```bash\n{step.command_linux}\n```")
            if step.command_windows:
                content_lines.append(f"**Windows**:\n```powershell\n{step.command_windows}\n```")

        raw_content = "\n".join(content_lines)

        # 4. create the document
        new_doc = DesignDocument(
            id=uuid.uuid4(),
            title=runbook.name,
            slug=f"runbook-{runbook.id}", # use runbook UUID in slug to be unique
            doc_type='runbook',
            format='markdown',
            raw_content=raw_content,
            source_type='manual', # or 'runbook_sync'
            status='active',
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        db.add(new_doc)
        db.commit()
        
        print(f"✅ Created DesignDocument for Runbook!")
        print(f"  ID: {new_doc.id}")
        print(f"  Title: {new_doc.title}")
        print(f"  Slug: {new_doc.slug}")
        print("-> It should now be visible in the Knowledge UI.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    create_runbook_document()
