"""
Data-access layer for users. Repositories talk to the DB only — no
business rules, no HTTP concerns. Services call repositories.
"""
import uuid
from typing import Optional

from app.extensions import db
from app.models import User


class UserRepository:
    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return db.session.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        return (
            db.session.query(User)
            .filter(db.func.lower(User.email) == email.lower(), User.deleted_at.is_(None))
            .first()
        )

    def email_exists(self, email: str) -> bool:
        return self.get_by_email(email) is not None

    def create(self, user: User) -> User:
        db.session.add(user)
        db.session.flush()
        return user

    def save(self, user: User) -> User:
        db.session.add(user)
        db.session.flush()
        return user
