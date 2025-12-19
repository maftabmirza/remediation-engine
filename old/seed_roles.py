"""Seed default roles into the database"""
from app.database import SessionLocal
from app.models import Role
from app.services.auth_service import ROLE_PERMISSIONS

def seed_roles():
    db = SessionLocal()
    try:
        # Check existing roles
        existing_roles = {r.name for r in db.query(Role).all()}
        print(f"Existing roles: {existing_roles}")
        
        # Add missing default roles
        for role_name, permissions in ROLE_PERMISSIONS.items():
            if role_name not in existing_roles:
                new_role = Role(
                    name=role_name,
                    description=f"Built-in {role_name} role",
                    permissions=list(permissions),
                    is_custom=False
                )
                db.add(new_role)
                print(f"Added role: {role_name} with {len(permissions)} permissions")
        
        db.commit()
        print("Roles seeded successfully")
        
    except Exception as e:
        print(f "Error seeding roles: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_roles()
