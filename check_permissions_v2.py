import sys
import os

# Ensure app is in path
sys.path.append('/app')

# Import main to ensure all models are registered
try:
    from app.main import app
except Exception as e:
    print(f"Error importing app: {e}")
    # Fallback: import some models manually if main fails to import clean
    import app.models 
    import app.models_application
    import app.models_troubleshooting

from app.database import get_db
from app.models import Role, User

def check():
    print("Checking permissions...", flush=True)
    try:
        db = next(get_db())
        
        roles = db.query(Role).all()
        for r in roles:
            print(f"Role: {r.name}", flush=True)
            print(f"  Permissions: {r.permissions}", flush=True)
            if "pii_view_config" in r.permissions:
                print("  -> pii_view_config: PRESENT", flush=True)
            else:
                print("  -> pii_view_config: MISSING", flush=True)
            print("-" * 20, flush=True)

    except Exception as e:
        print(f"An error occurred: {e}", flush=True)

        if admin_role:
            print(f"Admin permissions: {admin_role.permissions}")
            
            permissions_to_add = [
                "pii_view_config",
                "pii_edit_config",
                "pii_read_logs", 
                "pii_report_false_positive"
            ]
            
            missing = [p for p in permissions_to_add if p not in admin_role.permissions]
            
            if missing:
                print(f"Missing permissions: {missing}")
                print("Attempting to fix permissions...")
                perms = set(admin_role.permissions)
                for p in missing:
                    perms.add(p)
                
                admin_role.permissions = list(perms)
                db.commit()
                print("Permissions updated successfully!")
                print(f"New Admin permissions: {admin_role.permissions}")
            else:
                print("All PII permissions are PRESENT")
        else:
            print("Admin role NOT FOUND")
            # Try to list all roles
            roles = db.query(Role).all()
            print(f"Available roles: {[r.name for r in roles]}")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    check()
