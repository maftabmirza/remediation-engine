from app.database import SessionLocal
from app.models import User, Role
from app.core.security import get_password_hash
# Import all models to ensure registry is populated
import app.models_chat
import app.models_knowledge
import app.models_troubleshooting
import app.models_application
import app.models_remediation
import app.models_agent
import app.models_ai_helper
import app.models_dashboards
import app.models_group
import app.models_itsm
import app.models_learning
import app.models_runbook_acl
import app.models_scheduler

db = SessionLocal()

# Check/Create Admin Role
admin_role = db.query(Role).filter(Role.name == "admin").first()
if not admin_role:
    print("Creating admin role...")
    admin_role = Role(name="admin", description="Administrator with full access")
    db.add(admin_role)
    db.commit()

# Check/Create Admin User
user = db.query(User).filter(User.username == "admin").first()
if not user:
    print("Creating admin user...")
    user = User(
        username="admin",
        email="admin@example.com",
        full_name="System Administrator",
        hashed_password=get_password_hash("admin"),
        is_active=True,
        is_superuser=True
    )
    user.roles.append(admin_role)
    db.add(user)
    db.commit()
    print("Admin user created (password: admin)")
else:
    print("Admin user already exists. Resetting password to 'admin'...")
    user.hashed_password = get_password_hash("admin")
    user.is_active = True
    if admin_role not in user.roles:
        user.roles.append(admin_role)
    db.commit()
    print("Admin user updated.")

db.close()
