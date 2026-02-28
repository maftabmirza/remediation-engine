
import asyncio
import os
import sys
from uuid import UUID

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
# Import models to register them with SQLAlchemy
import app.models  # noqa: F401
import app.models_application  # noqa: F401
import app.models_application_knowledge  # noqa: F401
import app.models_knowledge  # noqa: F401
import app.models_learning  # noqa: F401
import app.models_dashboards  # noqa: F401
import app.models_agent  # noqa: F401
import app.models_changeset  # noqa: F401
from app.models_itsm import IncidentEvent
from app.services.llm_service import analyze_incident

async def test_analysis():
    settings = get_settings()
    db_url = settings.database_url.replace("postgres:", "localhost:")
    db_url = db_url.replace("@postgres", "@localhost")
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Get an incident
        incident = db.query(IncidentEvent).first()
        if not incident:
            print("No incidents found")
            return

        with open("tests/manual_test_result.txt", "w", encoding="utf-8") as f:
            f.write(f"Analyzing incident: {incident.title} ({incident.id})\n")
            
            # Analyze
            try:
                analysis, recommendations, provider = await analyze_incident(db, incident)
                f.write("\n--- Analysis Result ---\n")
                f.write(analysis[:500] + "...\n")
                f.write("\n--- Recommendations ---\n")
                f.write(str(recommendations) + "\n")
                f.write(f"\nProvider: {provider.name}\n")
                print("Analysis complete. See tests/manual_test_result.txt")
                
            except Exception as e:
                f.write(f"Analysis failed: {str(e)}\n")
                print(f"Analysis failed: {e}")
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_analysis())
