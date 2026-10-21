import uuid
from typing import Optional

from app.extensions import db
from app.models import InterviewTemplate, InterviewTemplateRound


class InterviewTemplateRepository:
    def get_by_id(
        self, template_id: uuid.UUID, *, institute_id: uuid.UUID
    ) -> Optional[InterviewTemplate]:
        return (
            db.session.query(InterviewTemplate)
            .filter(
                InterviewTemplate.id == template_id,
                InterviewTemplate.institute_id == institute_id,
                InterviewTemplate.deleted_at.is_(None),
            )
            .first()
        )

    def get_by_name(self, name: str, *, institute_id: uuid.UUID) -> Optional[InterviewTemplate]:
        return (
            db.session.query(InterviewTemplate)
            .filter(
                db.func.lower(InterviewTemplate.name) == name.lower(),
                InterviewTemplate.institute_id == institute_id,
                InterviewTemplate.deleted_at.is_(None),
            )
            .first()
        )

    def get_default(self, *, institute_id: uuid.UUID) -> Optional[InterviewTemplate]:
        return (
            db.session.query(InterviewTemplate)
            .filter(
                InterviewTemplate.institute_id == institute_id,
                InterviewTemplate.is_default.is_(True),
                InterviewTemplate.deleted_at.is_(None),
            )
            .first()
        )

    def list_paginated(
        self, *, institute_id: uuid.UUID, page: int, per_page: int
    ) -> tuple[list[InterviewTemplate], int]:
        query = db.session.query(InterviewTemplate).filter(
            InterviewTemplate.institute_id == institute_id,
            InterviewTemplate.deleted_at.is_(None),
        )
        total = query.count()
        items = (
            query.order_by(InterviewTemplate.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total

    def create(self, template: InterviewTemplate) -> InterviewTemplate:
        db.session.add(template)
        db.session.flush()
        return template

    def save(self, template: InterviewTemplate) -> InterviewTemplate:
        db.session.add(template)
        db.session.flush()
        return template

    def replace_rounds(
        self, template: InterviewTemplate, rounds: list[InterviewTemplateRound]
    ) -> None:
        for existing in list(template.rounds):
            db.session.delete(existing)
        db.session.flush()
        for r in rounds:
            r.template_id = template.id
            db.session.add(r)
        db.session.flush()
        # template.rounds is lazy="joined" and was populated before this
        # call; force a reload so the caller's in-memory object reflects
        # the new set immediately (e.g. for serializing the response).
        db.session.expire(template, ["rounds"])
