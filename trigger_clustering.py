#!/usr/bin/env python3
"""
Manual clustering trigger script
"""
from app.database import SessionLocal
from app.services.clustering_worker import cluster_recent_alerts

print("Starting manual clustering job...")
db = SessionLocal()

try:
    cluster_recent_alerts(db)
    print("✓ Clustering job completed successfully")
except Exception as e:
    print(f"✗ Clustering job failed: {e}")
finally:
    db.close()
