import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import SessionLocal, settings
from app.models import Role
from app.models_ai import AIPermission

# Import all models to ensure relationships are registered
try:
    from app.models import User, Alert
    import app.models_agent
    import app.models_agent_pool
    import app.models_application
    import app.models_application_knowledge
    import app.models_changeset
    import app.models_dashboards
    import app.models_group
    import app.models_iteration
    import app.models_itsm
    import app.models_knowledge
    import app.models_learning
    import app.models_remediation
    import app.models_revive
    import app.models_runbook_acl
    import app.models_scheduler
    import app.models_troubleshooting
except ImportError as e:
    print(f"DEBUG: Import Error: {e}")
    import traceback
    traceback.print_exc()



ROLES = ["admin", "operator", "engineer", "viewer"]

PERMISSIONS = {
    "admin": [
        {"pillar": "inquiry", "permission": "allow"},
        {"pillar": "troubleshooting", "permission": "allow"},
        {"pillar": "revive", "permission": "allow"},
    ],
    "operator": [
        {"pillar": "inquiry", "permission": "allow"},
        {"pillar": "troubleshooting", "permission": "allow"},
        {"pillar": "revive", "tool_category": "grafana", "tool_name": "search_dashboards", "permission": "allow"},
        {"pillar": "revive", "tool_category": "grafana", "tool_name": "create_dashboard", "permission": "confirm"},
        {"pillar": "revive", "tool_category": "grafana", "tool_name": "delete_dashboard", "permission": "deny"},
        {"pillar": "revive", "tool_category": "aiops", "tool_name": "list_runbooks", "permission": "allow"},
        {"pillar": "revive", "tool_category": "aiops", "tool_name": "execute_runbook", "permission": "confirm"},
    ],
    "engineer": [
        {"pillar": "inquiry", "permission": "allow"},
        {"pillar": "troubleshooting", "permission": "allow"},
        {"pillar": "revive", "tool_category": "grafana", "permission": "allow"},
        {"pillar": "revive", "tool_category": "aiops", "permission": "allow"},
    ],
    "viewer": [
        {"pillar": "inquiry", "permission": "allow"},
        {"pillar": "troubleshooting", "permission": "allow"},
        {"pillar": "revive", "permission": "deny"},
        {"pillar": "revive", "tool_category": "grafana", "tool_name": "search_dashboards", "permission": "allow"},
    ]
}

def seed():
    # Allow override
    db_url = os.environ.get("DATABASE_URL", settings.database_url)
    print(f"DEBUG: Connecting to: {db_url}")
    
    # Create local engine/session
    engine = create_engine(db_url)
    SessionLocalCustom = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocalCustom()
    
    try:
        role_map = {}
        
        # 1. Seed Roles
        for role_name in ROLES:
            role = db.query(Role).filter(Role.name == role_name).first()
            
            if not role:
                print(f"Creating role: {role_name}")
                role = Role(name=role_name, description=f"Default {role_name} role", permissions=[])
                db.add(role)
                db.commit()
                db.refresh(role)
            else:
                print(f"Role exists: {role_name}")
            
            role_map[role_name] = role.id

        # 2. Seed Permissions
        count = 0
        for role_name, perms in PERMISSIONS.items():
            role_id = role_map.get(role_name)
            if not role_id: 
                print(f"Skipping permissions for {role_name} (role not found)")
                continue

            print(f"Seeding permissions for {role_name}...")
            for p in perms:
                pillar = p["pillar"]
                category = p.get("tool_category")
                name = p.get("tool_name")
                permission = p["permission"]

                # Check existence
                query = db.query(AIPermission).filter(
                    AIPermission.role_id == role_id,
                    AIPermission.pillar == pillar
                )
                if category is not None:
                     query = query.filter(AIPermission.tool_category == category)
                else:
                     query = query.filter(AIPermission.tool_category.is_(None))
                
                if name is not None:
                     query = query.filter(AIPermission.tool_name == name)
                else:
                     query = query.filter(AIPermission.tool_name.is_(None))

                existing = query.first()

                if not existing:
                    new_perm = AIPermission(
                        role_id=role_id,
                        pillar=pillar,
                        tool_category=category,
                        tool_name=name,
                        permission=permission
                    )
                    db.add(new_perm)
                    count += 1
        
        db.commit()
        print(f"Seeding complete. Added {count} new permission rules.")
    
    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
