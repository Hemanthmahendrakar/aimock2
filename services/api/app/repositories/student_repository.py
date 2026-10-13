import uuid
from typing import Optional

from app.extensions import db
from app.models import Student


class StudentRepository:
    def get_by_id(self, student_id: uuid.UUID, *, institute_id: uuid.UUID) -> Optional[Student]:
        """
        Always scoped by institute_id — this is the enforcement point
        that stops one institute from ever loading another's student by
        guessing/brute-forcing a UUID.
        """
        return (
            db.session.query(Student)
            .filter(
                Student.id == student_id,
                Student.institute_id == institute_id,
                Student.deleted_at.is_(None),
            )
            .first()
        )

    def get_by_email(self, email: str, *, institute_id: uuid.UUID) -> Optional[Student]:
        return (
            db.session.query(Student)
            .filter(
                db.func.lower(Student.email) == email.lower(),
                Student.institute_id == institute_id,
                Student.deleted_at.is_(None),
            )
            .first()
        )

    def get_by_roll_number(
        self, roll_number: str, *, institute_id: uuid.UUID
    ) -> Optional[Student]:
        return (
            db.session.query(Student)
            .filter(
                Student.roll_number == roll_number,
                Student.institute_id == institute_id,
                Student.deleted_at.is_(None),
            )
            .first()
        )

    def list_paginated(
        self,
        *,
        institute_id: uuid.UUID,
        page: int,
        per_page: int,
        search: Optional[str] = None,
        department: Optional[str] = None,
        batch: Optional[str] = None,
        status: Optional[str] = None,
    ) -> tuple[list[Student], int]:
        query = db.session.query(Student).filter(
            Student.institute_id == institute_id, Student.deleted_at.is_(None)
        )

        if search:
            like = f"%{search.lower()}%"
            query = query.filter(
                db.or_(
                    db.func.lower(Student.name).like(like),
                    db.func.lower(Student.email).like(like),
                    db.func.lower(Student.roll_number).like(like),
                )
            )
        if department:
            query = query.filter(Student.department == department)
        if batch:
            query = query.filter(Student.batch == batch)
        if status:
            query = query.filter(Student.status == status)

        total = query.count()
        items = (
            query.order_by(Student.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total

    def create(self, student: Student) -> Student:
        db.session.add(student)
        db.session.flush()
        return student

    def save(self, student: Student) -> Student:
        db.session.add(student)
        db.session.flush()
        return student

    def bulk_create(self, students: list[Student]) -> None:
        db.session.add_all(students)
        db.session.flush()
