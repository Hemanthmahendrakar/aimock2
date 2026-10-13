"""
CLI utility for one-off admin tasks (seeding roles, etc).
Usage: python manage.py seed-roles
"""
import sys

from app import create_app
from app.extensions import db
from app.models import Role, RoleName


def seed_roles():
    app = create_app()
    with app.app_context():
        for name in RoleName.ALL:
            if not db.session.query(Role).filter(Role.name == name).first():
                db.session.add(Role(name=name))
                print(f"Created role: {name}")
        db.session.commit()
        print("Roles seeded.")


COMMANDS = {"seed-roles": seed_roles}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: python manage.py [{'|'.join(COMMANDS)}]")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()
