
from app.database import SessionLocal
# Import all models to ensure relationships are registered
try:
    from app.models import User
    import app.models_remediation
    import app.models_chat
    import app.models_knowledge
    import app.models_troubleshooting
    import app.models_agent
    import app.models_revive
    import app.models_application
    import app.models_dashboards
    import app.models_group
    import app.models_itsm
    import app.models_learning
    import app.models_runbook_acl
    import app.models_scheduler
    import app.models_observability
except ImportError:
    pass

from app.services.auth_service import create_user

def check_and_fix_admin():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "admin").first()
        if user:
            print(f"User FOUND: {user.username} (ID: {user.id})")
            print(f"Is Active: {user.is_active}")
            print(f"Role: {user.role}")
        else:
            print("User admin NOT FOUND. Creating...")
            try:
                # Create admin user with default password 'admin'
                new_user = create_user(db, "admin", "admin", role="owner")
                print(f"Admin user created successfully. ID: {new_user.id}")
                print("Username: admin")
                print("Password: admin")
            except Exception as e:
                print(f"Failed to create admin user: {e}")
                
    except Exception as e:
        print(f"Error checking user: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_and_fix_admin()
