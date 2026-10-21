import uuid
from typing import Optional

from app.extensions import db
from app.models import Campaign, CampaignStudent, Student


class CampaignRepository:
    def get_by_id(
        self, campaign_id: uuid.UUID, *, institute_id: uuid.UUID
    ) -> Optional[Campaign]:
        return (
            db.session.query(Campaign)
            .filter(
                Campaign.id == campaign_id,
                Campaign.institute_id == institute_id,
                Campaign.deleted_at.is_(None),
            )
            .first()
        )

    def list_paginated(
        self,
        *,
        institute_id: uuid.UUID,
        page: int,
        per_page: int,
        status: Optional[str] = None,
    ) -> tuple[list[Campaign], int]:
        query = db.session.query(Campaign).filter(
            Campaign.institute_id == institute_id, Campaign.deleted_at.is_(None)
        )
        if status:
            query = query.filter(Campaign.status == status)

        total = query.count()
        items = (
            query.order_by(Campaign.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total

    def create(self, campaign: Campaign) -> Campaign:
        db.session.add(campaign)
        db.session.flush()
        return campaign

    def save(self, campaign: Campaign) -> Campaign:
        db.session.add(campaign)
        db.session.flush()
        return campaign

    # ------------------------------------------------------------------
    # Roster (campaign_students)
    # ------------------------------------------------------------------
    def get_assignment(
        self, campaign_id: uuid.UUID, student_id: uuid.UUID
    ) -> Optional[CampaignStudent]:
        return (
            db.session.query(CampaignStudent)
            .filter(
                CampaignStudent.campaign_id == campaign_id,
                CampaignStudent.student_id == student_id,
            )
            .first()
        )

    def assign_students(self, campaign_id: uuid.UUID, student_ids: list[uuid.UUID]) -> None:
        rows = [
            CampaignStudent(campaign_id=campaign_id, student_id=sid) for sid in student_ids
        ]
        db.session.add_all(rows)
        db.session.flush()

    def unassign_student(self, campaign_id: uuid.UUID, student_id: uuid.UUID) -> bool:
        row = self.get_assignment(campaign_id, student_id)
        if row is None:
            return False
        db.session.delete(row)
        db.session.flush()
        return True

    def count_assigned(self, campaign_id: uuid.UUID) -> int:
        return (
            db.session.query(CampaignStudent)
            .filter(CampaignStudent.campaign_id == campaign_id)
            .count()
        )

    def list_assigned_students(
        self, campaign_id: uuid.UUID, *, page: int, per_page: int
    ) -> tuple[list[Student], int]:
        query = (
            db.session.query(Student)
            .join(CampaignStudent, CampaignStudent.student_id == Student.id)
            .filter(CampaignStudent.campaign_id == campaign_id, Student.deleted_at.is_(None))
        )
        total = query.count()
        items = (
            query.order_by(Student.name.asc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total

    def already_assigned_student_ids(
        self, campaign_id: uuid.UUID, student_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        rows = (
            db.session.query(CampaignStudent.student_id)
            .filter(
                CampaignStudent.campaign_id == campaign_id,
                CampaignStudent.student_id.in_(student_ids),
            )
            .all()
        )
        return {r[0] for r in rows}
