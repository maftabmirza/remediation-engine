from app.database import get_db
from app.models import Role
from sqlalchemy.orm import Session

def check_permissions():
    db = next(get_db())
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if admin_role:
        print(f"Admin permissions: {admin_role.permissions}")
        if "pii_view_config" in admin_role.permissions:
            print("pii_view_config is PRESENT")
        else:
            print("pii_view_config is MISSING")
    else:
        print("Admin role NOT FOUND")

if __name__ == "__main__":
    check_permissions()
