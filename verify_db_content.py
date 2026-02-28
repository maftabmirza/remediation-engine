from app.database import SessionLocal
# Import all models to resolve relationships
from app.models import *
from app.models_agent import *
from app.models_application import *
from app.models_chat import *
from app.models_dashboards import *
from app.models_group import *
from app.models_itsm import *
from app.models_knowledge import *
from app.models_learning import *
from app.models_remediation import RunbookStep, Runbook
from app.models_runbook_acl import *
from app.models_scheduler import *
from app.models_troubleshooting import *

from sqlalchemy import select

def verify_db():
    db = SessionLocal()
    try:
        # Find the runbook
        stmt = select(Runbook).where(Runbook.name == "Service Recovery (Legacy Mode vs Native)")
        runbook = db.execute(stmt).scalars().first()
        
        if not runbook:
            print("Runbook not found in DB")
            return

        print(f"Runbook ID: {runbook.id}")
        
        # Get steps manually
        steps = db.query(RunbookStep).filter(RunbookStep.runbook_id == runbook.id).order_by(RunbookStep.step_order).all()
        
        print("\n--- DB Steps Content ---")
        for step in steps:
            print(f"Step {step.step_order}: {step.name}")
            # Access attributes directly - if they don't exist on the object, this will fail
            # verifying if SQLAlchemy model has them
            print(f"  run_if_variable: {getattr(step, 'run_if_variable', 'ATTR_MISSING')}")
            print(f"  run_if_value: {getattr(step, 'run_if_value', 'ATTR_MISSING')}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_db()
