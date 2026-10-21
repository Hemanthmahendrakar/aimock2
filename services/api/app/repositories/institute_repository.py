import uuid
from typing import Optional

from app.extensions import db
from app.models import Institute


class InstituteRepository:
    def get_by_id(self, institute_id: uuid.UUID) -> Optional[Institute]:
        return db.session.get(Institute, institute_id)

    def get_by_email(self, email: str) -> Optional[Institute]:
        return (
            db.session.query(Institute)
            .filter(db.func.lower(Institute.email) == email.lower())
            .first()
        )

    def email_exists(self, email: str) -> bool:
        return self.get_by_email(email) is not None

    def create(self, institute: Institute) -> Institute:
        db.session.add(institute)
        db.session.flush()
        return institute

    def save(self, institute: Institute) -> Institute:
        db.session.add(institute)
        db.session.flush()
        return institute
