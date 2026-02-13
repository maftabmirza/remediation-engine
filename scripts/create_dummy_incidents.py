import sys
import os
import logging
import random
import uuid
from datetime import datetime, timezone, timedelta

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Override settings to use localhost for host execution
from app.config import get_settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

settings = get_settings()
db_url = settings.database_url.replace("postgres:", "localhost:")
db_url = db_url.replace("@postgres", "@localhost")

# Re-create engine and session factory
engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from app.models_itsm import IncidentEvent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_dummy_incidents():
    db = SessionLocal()
    try:
        logger.info("Generating 10 dummy incidents...")
        
        statuses = ['New', 'In Progress', 'Resolved', 'Closed', 'On Hold']
        severities = ['Critical', 'High', 'Medium', 'Low']
        priorities = ['P1', 'P2', 'P3', 'P4']
        services = ['Payment Service', 'Auth Service', 'Frontend App', 'Database Cluster', 'Search Engine']
        incident_types = ['Performance Degradation', 'Service Outage', 'Data Inconsistency', 'API Failure', 'UI Glitch']
        
        for i in range(1, 11):
            # Generate random data
            incident_id = f"PROJ-{random.randint(1000, 9999)}"
            title = f"{random.choice(incident_types)} in {random.choice(services)}"
            created_at = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 7), hours=random.randint(0, 23))
            status = random.choice(statuses)
            
            # Resolve if resolved/closed
            resolved_at = None
            if status in ['Resolved', 'Closed']:
                resolved_at = created_at + timedelta(hours=random.randint(1, 48))
                
            incident = IncidentEvent(
                incident_id=incident_id,
                title=title,
                description=f"Automated alert detected {title}. impacting users in region {random.choice(['US-East', 'EU-West', 'APAC'])}.",
                status=status,
                severity=random.choice(severities),
                priority=random.choice(priorities),
                service_name=random.choice(services),
                created_at=created_at,
                resolved_at=resolved_at,
                assignee=f"user{i}@example.com",
                source="dummy_script",
                incident_metadata={
                    "jira_key": incident_id,
                    "jira_project": "PROJ",
                    "components": ["backend", "api"],
                    "custom_field_123": "Value " + str(i)
                },
                is_open=status not in ['Resolved', 'Closed', 'Canceled']
            )
            
            # Check for existing
            existing = db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident_id).first()
            if not existing:
                db.add(incident)
                logger.info(f"Created incident: {incident_id} - {title}")
            else:
                logger.info(f"Skipping existing incident: {incident_id}")
                
        db.commit()
        logger.info("🎉 Successfully generated 10 dummy incidents!")
        
    except Exception as e:
        logger.error(f"❌ Failed to generate incidents: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_dummy_incidents()
