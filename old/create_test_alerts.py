import os
import sys
import uuid
from sqlalchemy import create_engine, text

# Database Config
DATABASE_URL = "postgresql://aiops:aiops_secure_password@localhost:5432/aiops"

print("Creating test alerts using raw SQL...")

try:
    engine = create_engine(DATABASE_URL)
    
    alert_id = str(uuid.uuid4())
    alert_api_id = str(uuid.uuid4())
    alert_fe_id = str(uuid.uuid4())

    sql = text("""
    INSERT INTO alerts (id, alert_name, severity, status, instance, job, labels_json, annotations_json, timestamp, fingerprint, created_at)
    VALUES 
    (:id1, 'PostgreSQL Connection Refused', 'critical', 'firing', 'db-prod-01', 'postgres_exporter', '{"severity": "critical", "env": "prod"}', '{"summary": "Database refusing connections", "description": "Max connections reached"}', NOW(), 'test-db-raw-1', NOW()),
    (:id2, 'API High Error Rate', 'warning', 'firing', 'app-prod-01', 'api_server', '{"severity": "warning", "env": "prod"}', '{"summary": "API returning 500s", "description": "Error rate > 5%"}', NOW(), 'test-api-raw-1', NOW()),
    (:id3, 'Frontend 502 Bad Gateway', 'warning', 'firing', 'fe-prod-01', 'frontend', '{"severity": "warning", "env": "prod"}', '{"summary": "Frontend upstream error", "description": "502 responses"}', NOW(), 'test-fe-raw-1', NOW());
    """)

    with engine.connect() as conn:
        conn.execute(sql, {"id1": alert_id, "id2": alert_api_id, "id3": alert_fe_id})
        conn.commit()

    print(f"Successfully created 3 alerts.")
    print(f"Test Alert URL: http://localhost:8080/alerts/{alert_id}")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
