"""
Business logic for campaigns and their student roster. Every method
takes an institute_id that MUST already be g.current_institute_id.
"""
import uuid
from typing import Optional

from app.extensions import db
from app.models import Campaign, CampaignStatus, CampaignDifficulty
from app.repositories.campaign_repository import CampaignRepository
from app.repositories.student_repository import StudentRepository
from app.repositories.interview_template_repository import InterviewTemplateRepository
from app.services.audit_service import AuditService


class CampaignServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class CampaignNotFound(CampaignServiceError):
    def __init__(self):
        super().__init__("campaign_not_found", "Campaign not found.", 404)


class InvalidStatusTransition(CampaignServiceError):
    def __init__(self, *, current: str, target: str):
        super().__init__(
            "invalid_status_transition",
            f"Cannot move campaign from '{current}' to '{target}'.",
            409,
        )


# draft -> active -> completed; archived reachable from any non-archived state
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    CampaignStatus.DRAFT: {CampaignStatus.ACTIVE, CampaignStatus.ARCHIVED},
    CampaignStatus.ACTIVE: {CampaignStatus.COMPLETED, CampaignStatus.ARCHIVED},
    CampaignStatus.COMPLETED: {CampaignStatus.ARCHIVED},
    CampaignStatus.ARCHIVED: set(),
}


class CampaignService:
    def __init__(self):
        self.campaigns = CampaignRepository()
        self.students = StudentRepository()
        self.templates = InterviewTemplateRepository()
        self.audit = AuditService()

    # ------------------------------------------------------------------
    def _get_or_404(self, campaign_id: uuid.UUID, *, institute_id: uuid.UUID) -> Campaign:
        campaign = self.campaigns.get_by_id(campaign_id, institute_id=institute_id)
        if campaign is None:
            raise CampaignNotFound()
        return campaign

    def create(self, institute_id: uuid.UUID, *, data: dict) -> Campaign:
        from flask import current_app

        if data.get("difficulty") and data["difficulty"] not in CampaignDifficulty.ALL:
            raise CampaignServiceError("invalid_difficulty", "Invalid difficulty level.", 422)
        if data.get("question_source") and data["question_source"] not in ("ai", "custom", "mixed"):
            raise CampaignServiceError("invalid_question_source", "Question source must be ai, custom, or mixed.", 422)

        # Resolve an optional template first — its round config fills in
        # any field the caller didn't explicitly set. Precedence is:
        # explicit request value > template value > app.config default.
        template = None
        template_id_raw = data.get("interview_template_id")
        if template_id_raw:
            try:
                template_uuid = uuid.UUID(template_id_raw)
            except ValueError:
                raise CampaignServiceError(
                    "invalid_template_id", "Invalid interview_template_id.", 422
                )
            template = self.templates.get_by_id(template_uuid, institute_id=institute_id)
            if template is None:
                raise CampaignServiceError(
                    "template_not_found", "Interview template not found.", 404
                )

        rounds_by_type = {r.round_type: r for r in template.rounds} if template else {}

        def round_value(field: str, round_type: str, attr: str, config_key: str):
            if data.get(field) is not None:
                return data[field]
            r = rounds_by_type.get(round_type)
            if r is not None:
                val = getattr(r, attr)
                if val is not None:
                    return val
            return current_app.config[config_key]

        def round_optional(field: str, round_type: str, attr: str):
            if data.get(field) is not None:
                return data[field]
            r = rounds_by_type.get(round_type)
            return getattr(r, attr) if r is not None else None

        technical_categories = data.get("question_categories")
        if technical_categories is None:
            technical_categories = round_optional(
                "question_categories", "technical", "question_categories"
            ) or []

        evaluation_criteria = data.get("evaluation_criteria")
        if evaluation_criteria is None and rounds_by_type:
            # No explicit override: merge each round's criteria in,
            # keyed by round type, so nothing from the template is lost.
            evaluation_criteria = {
                round_type: r.evaluation_criteria
                for round_type, r in rounds_by_type.items()
                if r.evaluation_criteria
            }
        evaluation_criteria = evaluation_criteria or {}

        # Optional references must belong to this institute (or be in the shared company catalog).
        from app.models import Campus, Company
        company_id = None
        if data.get("company_id"):
            try: company_id = uuid.UUID(str(data["company_id"]))
            except (ValueError, TypeError): raise CampaignServiceError("invalid_company_id", "Invalid company_id.", 422)
            from sqlalchemy import or_
            company = Company.query.filter(Company.id == company_id, Company.deleted_at.is_(None), or_(Company.institute_id.is_(None), Company.institute_id == institute_id)).first()
            if company is None: raise CampaignServiceError("company_not_found", "Company not found.", 404)
        campus_id = None
        if data.get("campus_id"):
            try: campus_id = uuid.UUID(str(data["campus_id"]))
            except (ValueError, TypeError): raise CampaignServiceError("invalid_campus_id", "Invalid campus_id.", 422)
            campus = Campus.query.filter_by(id=campus_id, institute_id=institute_id, deleted_at=None).first()
            if campus is None: raise CampaignServiceError("campus_not_found", "Campus not found.", 404)

        campaign = Campaign(
            institute_id=institute_id,
            company_id=company_id,
            campus_id=campus_id,
            job_description=data.get("job_description"),
            question_source=data.get("question_source") or "ai",
            interview_template_id=template.id if template else None,
            name=data["name"],
            role=data["role"],
            experience_level=data.get("experience_level"),
            department=data.get("department"),
            batch=data.get("batch"),
            technical_duration_minutes=round_value(
                "technical_duration_minutes", "technical", "duration_minutes",
                "TECHNICAL_ROUND_DEFAULT_MINUTES",
            ),
            managerial_duration_minutes=round_value(
                "managerial_duration_minutes", "managerial", "duration_minutes",
                "MANAGERIAL_ROUND_DEFAULT_MINUTES",
            ),
            hr_duration_minutes=round_value(
                "hr_duration_minutes", "hr", "duration_minutes", "HR_ROUND_DEFAULT_MINUTES",
            ),
            technical_instructions=round_optional(
                "technical_instructions", "technical", "instructions"
            ),
            managerial_instructions=round_optional(
                "managerial_instructions", "managerial", "instructions"
            ),
            hr_instructions=round_optional("hr_instructions", "hr", "instructions"),
            interviewer_avatar=data.get("interviewer_avatar"),
            interviewer_voice=data.get("interviewer_voice"),
            interview_style=data.get("interview_style"),
            difficulty=data.get("difficulty") or CampaignDifficulty.MEDIUM,
            question_categories=technical_categories,
            evaluation_criteria=evaluation_criteria,
        )
        self.campaigns.create(campaign)
        self.audit.log(
            event_type="campaign.created", institute_id=institute_id,
            metadata={
                "campaign_id": str(campaign.id), "name": campaign.name,
                "interview_template_id": str(template.id) if template else None,
            },
        )
        db.session.commit()
        return campaign

    def get(self, campaign_id: uuid.UUID, *, institute_id: uuid.UUID) -> Campaign:
        return self._get_or_404(campaign_id, institute_id=institute_id)

    def list(
        self, *, institute_id: uuid.UUID, page: int, per_page: int, status: Optional[str] = None
    ) -> tuple[list[Campaign], int]:
        page = max(page, 1)
        per_page = min(max(per_page, 1), 100)
        return self.campaigns.list_paginated(
            institute_id=institute_id, page=page, per_page=per_page, status=status
        )

    def update(self, campaign_id: uuid.UUID, *, institute_id: uuid.UUID, data: dict) -> Campaign:
        campaign = self._get_or_404(campaign_id, institute_id=institute_id)

        if data.get("difficulty") and data["difficulty"] not in CampaignDifficulty.ALL:
            raise CampaignServiceError("invalid_difficulty", "Invalid difficulty level.", 422)
        if data.get("question_source") and data["question_source"] not in ("ai", "custom", "mixed"):
            raise CampaignServiceError("invalid_question_source", "Question source must be ai, custom, or mixed.", 422)

        from app.models import Campus, Company
        if data.get("company_id") is not None:
            from sqlalchemy import or_
            try: company_uuid = uuid.UUID(str(data["company_id"]))
            except (ValueError, TypeError): raise CampaignServiceError("invalid_company_id", "Invalid company_id.", 422)
            company = Company.query.filter(Company.id == company_uuid, Company.deleted_at.is_(None), or_(Company.institute_id.is_(None), Company.institute_id == institute_id)).first()
            if company is None: raise CampaignServiceError("company_not_found", "Company not found.", 404)
            data["company_id"] = company_uuid
        if data.get("campus_id") is not None:
            try: campus_uuid = uuid.UUID(str(data["campus_id"]))
            except (ValueError, TypeError): raise CampaignServiceError("invalid_campus_id", "Invalid campus_id.", 422)
            if Campus.query.filter_by(id=campus_uuid, institute_id=institute_id, deleted_at=None).first() is None:
                raise CampaignServiceError("campus_not_found", "Campus not found.", 404)
            data["campus_id"] = campus_uuid

        for key in (
            "name", "role", "experience_level", "department", "batch", "job_description", "company_id", "campus_id", "question_source",
            "technical_duration_minutes", "managerial_duration_minutes", "hr_duration_minutes",
            "technical_instructions", "managerial_instructions", "hr_instructions",
            "interviewer_avatar", "interviewer_voice", "interview_style",
            "difficulty", "question_categories", "evaluation_criteria",
        ):
            if key in data and data[key] is not None:
                setattr(campaign, key, data[key])

        self.campaigns.save(campaign)
        self.audit.log(
            event_type="campaign.updated", institute_id=institute_id,
            metadata={"campaign_id": str(campaign.id), "fields": list(data.keys())},
        )
        db.session.commit()
        return campaign

    def delete(self, campaign_id: uuid.UUID, *, institute_id: uuid.UUID) -> None:
        campaign = self._get_or_404(campaign_id, institute_id=institute_id)
        campaign.soft_delete()
        self.campaigns.save(campaign)
        self.audit.log(
            event_type="campaign.deleted", institute_id=institute_id,
            metadata={"campaign_id": str(campaign.id)},
        )
        db.session.commit()

    def transition_status(
        self, campaign_id: uuid.UUID, *, institute_id: uuid.UUID, target_status: str
    ) -> Campaign:
        campaign = self._get_or_404(campaign_id, institute_id=institute_id)

        allowed = _ALLOWED_TRANSITIONS.get(campaign.status, set())
        if target_status not in allowed:
            raise InvalidStatusTransition(current=campaign.status, target=target_status)

        old_status = campaign.status
        campaign.status = target_status
        self.campaigns.save(campaign)
        self.audit.log(
            event_type="campaign.status_changed", institute_id=institute_id,
            metadata={
                "campaign_id": str(campaign.id), "from": old_status, "to": target_status,
            },
        )
        db.session.commit()
        return campaign

    # ------------------------------------------------------------------
    # Roster
    # ------------------------------------------------------------------
    def assign_students(
        self, campaign_id: uuid.UUID, *, institute_id: uuid.UUID, student_ids: list[str]
    ) -> dict:
        campaign = self._get_or_404(campaign_id, institute_id=institute_id)

        valid_ids: list[uuid.UUID] = []
        invalid: list[str] = []
        for raw_id in student_ids:
            try:
                valid_ids.append(uuid.UUID(raw_id))
            except ValueError:
                invalid.append(raw_id)

        # Confirm each student actually belongs to this institute — the
        # trust boundary here is the same as everywhere else: never
        # assume a client-supplied ID is valid just because it parses.
        existing_in_institute: list[uuid.UUID] = []
        not_found: list[str] = []
        for sid in valid_ids:
            student = self.students.get_by_id(sid, institute_id=institute_id)
            if student is None:
                not_found.append(str(sid))
            else:
                existing_in_institute.append(sid)

        already_assigned = self.campaigns.already_assigned_student_ids(
            campaign.id, existing_in_institute
        )
        to_assign = [sid for sid in existing_in_institute if sid not in already_assigned]

        if to_assign:
            self.campaigns.assign_students(campaign.id, to_assign)

        self.audit.log(
            event_type="campaign.students_assigned",
            institute_id=institute_id,
            metadata={
                "campaign_id": str(campaign.id),
                "assigned": len(to_assign),
                "already_assigned": len(already_assigned),
                "not_found": len(not_found),
                "invalid": len(invalid),
            },
        )
        db.session.commit()

        return {
            "assigned": len(to_assign),
            "already_assigned": len(already_assigned),
            "not_found": not_found,
            "invalid_ids": invalid,
        }

    def unassign_student(
        self, campaign_id: uuid.UUID, student_id: uuid.UUID, *, institute_id: uuid.UUID
    ) -> None:
        campaign = self._get_or_404(campaign_id, institute_id=institute_id)
        removed = self.campaigns.unassign_student(campaign.id, student_id)
        if not removed:
            raise CampaignServiceError(
                "assignment_not_found", "Student is not assigned to this campaign.", 404
            )
        self.audit.log(
            event_type="campaign.student_unassigned",
            institute_id=institute_id,
            metadata={"campaign_id": str(campaign.id), "student_id": str(student_id)},
        )
        db.session.commit()

    def list_assigned_students(
        self, campaign_id: uuid.UUID, *, institute_id: uuid.UUID, page: int, per_page: int
    ) -> tuple[list, int]:
        campaign = self._get_or_404(campaign_id, institute_id=institute_id)
        page = max(page, 1)
        per_page = min(max(per_page, 1), 100)
        return self.campaigns.list_assigned_students(campaign.id, page=page, per_page=per_page)
