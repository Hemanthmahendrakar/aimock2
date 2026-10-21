"""
Business logic for interview templates. Every method takes an
institute_id that MUST already be g.current_institute_id.
"""
import uuid

from app.extensions import db
from app.models import InterviewTemplate, InterviewTemplateRound
from app.repositories.interview_template_repository import InterviewTemplateRepository
from app.services.audit_service import AuditService


class InterviewTemplateServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class TemplateNotFound(InterviewTemplateServiceError):
    def __init__(self):
        super().__init__("template_not_found", "Interview template not found.", 404)


class DuplicateTemplateName(InterviewTemplateServiceError):
    def __init__(self):
        super().__init__(
            "duplicate_template_name", "A template with this name already exists.", 409
        )


class InterviewTemplateService:
    def __init__(self):
        self.templates = InterviewTemplateRepository()
        self.audit = AuditService()

    def _get_or_404(
        self, template_id: uuid.UUID, *, institute_id: uuid.UUID
    ) -> InterviewTemplate:
        template = self.templates.get_by_id(template_id, institute_id=institute_id)
        if template is None:
            raise TemplateNotFound()
        return template

    def _build_rounds(self, round_configs: list[dict]) -> list[InterviewTemplateRound]:
        # sequence_order follows the canonical technical -> managerial
        # -> hr ordering regardless of the order they arrived in the
        # request, since that's the fixed round sequence everywhere
        # else in the app (see the INTERVIEW flow in the original spec).
        order_map = {"technical": 1, "managerial": 2, "hr": 3}
        rounds = []
        for cfg in round_configs:
            rounds.append(
                InterviewTemplateRound(
                    round_type=cfg["round_type"],
                    sequence_order=order_map.get(cfg["round_type"], 99),
                    duration_minutes=cfg["duration_minutes"],
                    question_categories=cfg.get("question_categories") or [],
                    evaluation_criteria=cfg.get("evaluation_criteria") or {},
                    instructions=cfg.get("instructions"),
                )
            )
        return rounds

    def _apply_default_flag(
        self, template: InterviewTemplate, *, is_default: bool, institute_id: uuid.UUID
    ) -> None:
        if not is_default:
            template.is_default = False
            return
        current_default = self.templates.get_default(institute_id=institute_id)
        if current_default is not None and current_default.id != template.id:
            current_default.is_default = False
            self.templates.save(current_default)
        template.is_default = True

    # ------------------------------------------------------------------
    def create(self, institute_id: uuid.UUID, *, data: dict) -> InterviewTemplate:
        if self.templates.get_by_name(data["name"], institute_id=institute_id):
            raise DuplicateTemplateName()

        template = InterviewTemplate(
            institute_id=institute_id,
            name=data["name"],
            description=data.get("description"),
        )
        self._apply_default_flag(
            template, is_default=data.get("is_default", False), institute_id=institute_id
        )
        self.templates.create(template)

        rounds = self._build_rounds(data.get("rounds") or [])
        for r in rounds:
            r.template_id = template.id
        db.session.add_all(rounds)
        db.session.flush()

        self.audit.log(
            event_type="interview_template.created",
            institute_id=institute_id,
            metadata={"template_id": str(template.id), "name": template.name},
        )
        db.session.commit()
        return template

    def get(self, template_id: uuid.UUID, *, institute_id: uuid.UUID) -> InterviewTemplate:
        return self._get_or_404(template_id, institute_id=institute_id)

    def list(
        self, *, institute_id: uuid.UUID, page: int, per_page: int
    ) -> tuple[list[InterviewTemplate], int]:
        page = max(page, 1)
        per_page = min(max(per_page, 1), 100)
        return self.templates.list_paginated(
            institute_id=institute_id, page=page, per_page=per_page
        )

    def update(
        self, template_id: uuid.UUID, *, institute_id: uuid.UUID, data: dict
    ) -> InterviewTemplate:
        template = self._get_or_404(template_id, institute_id=institute_id)

        new_name = data.get("name")
        if new_name and new_name.lower() != template.name.lower():
            existing = self.templates.get_by_name(new_name, institute_id=institute_id)
            if existing and existing.id != template.id:
                raise DuplicateTemplateName()
            template.name = new_name

        if "description" in data and data["description"] is not None:
            template.description = data["description"]

        if "is_default" in data and data["is_default"] is not None:
            self._apply_default_flag(
                template, is_default=data["is_default"], institute_id=institute_id
            )

        if data.get("rounds") is not None:
            rounds = self._build_rounds(data["rounds"])
            self.templates.replace_rounds(template, rounds)

        self.templates.save(template)
        self.audit.log(
            event_type="interview_template.updated",
            institute_id=institute_id,
            metadata={"template_id": str(template.id), "fields": list(data.keys())},
        )
        db.session.commit()
        return template

    def delete(self, template_id: uuid.UUID, *, institute_id: uuid.UUID) -> None:
        template = self._get_or_404(template_id, institute_id=institute_id)
        template.soft_delete()
        self.templates.save(template)
        self.audit.log(
            event_type="interview_template.deleted",
            institute_id=institute_id,
            metadata={"template_id": str(template.id)},
        )
        db.session.commit()
