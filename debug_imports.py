
import sys
import os

# Add local path to sys.path
sys.path.append(os.getcwd())

print("1. Importing app.models...")
try:
    from app.models import Alert, User, LLMProvider, AuditLog, IncidentMetrics
    print("   Success.")
except Exception as e:
    print(f"   Failed: {e}")
    sys.exit(1)

print("2. Importing app.models_remediation...")
try:
    from app.models_remediation import RunbookExecution
    print("   Success.")
except Exception as e:
    print(f"   Failed: {e}")
    sys.exit(1)

print("3. Importing app.services.alert_clustering_service...")
try:
    from app.services.alert_clustering_service import AlertClusteringService
    print("   Success.")
except Exception as e:
    print(f"   Failed: {e}")
    sys.exit(1)

print("4. Instantiating AlertClusteringService (mock db)...")
try:
    class MockDB:
        def __init__(self):
            pass
    service = AlertClusteringService(MockDB())
    print("   Success.")
except Exception as e:
    print(f"   Failed: {e}")
    sys.exit(1)

print("All imports successful.")
