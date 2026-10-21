"""
Plain-dict serializers shared across routes. Kept separate from
pydantic request schemas since these go the other direction
(model -> JSON), not input validation.
"""
from app.models import Student, Campaign, InterviewTemplate


def serialize_student(student: Student) -> dict:
    return {
        "id": str(student.id),
        "name": student.name,
        "email": student.email,
        "roll_number": student.roll_number,
        "department": student.department,
        "batch": student.batch,
        "phone": student.phone,
        "campus_id": str(student.campus_id) if getattr(student, "campus_id", None) else None,
        "course": getattr(student, "course", None),
        "graduation_year": getattr(student, "graduation_year", None),
        "experience_level": getattr(student, "experience_level", None),
        "status": student.status,
        "created_at": student.created_at.isoformat() if student.created_at else None,
        "updated_at": student.updated_at.isoformat() if student.updated_at else None,
    }


def serialize_campaign(campaign: Campaign, *, assigned_student_count: int | None = None) -> dict:
    result = {
        "id": str(campaign.id),
        "name": campaign.name,
        "company_id": str(campaign.company_id) if getattr(campaign, "company_id", None) else None,
        "campus_id": str(campaign.campus_id) if getattr(campaign, "campus_id", None) else None,
        "job_description": getattr(campaign, "job_description", None),
        "question_source": getattr(campaign, "question_source", "ai"),
        "role": campaign.role,
        "experience_level": campaign.experience_level,
        "department": campaign.department,
        "batch": campaign.batch,
        "interview_template_id": str(campaign.interview_template_id)
        if campaign.interview_template_id else None,
        "technical_duration_minutes": campaign.technical_duration_minutes,
        "managerial_duration_minutes": campaign.managerial_duration_minutes,
        "hr_duration_minutes": campaign.hr_duration_minutes,
        "total_duration_minutes": campaign.total_duration_minutes,
        "technical_instructions": campaign.technical_instructions,
        "managerial_instructions": campaign.managerial_instructions,
        "hr_instructions": campaign.hr_instructions,
        "interviewer_avatar": campaign.interviewer_avatar,
        "interviewer_voice": campaign.interviewer_voice,
        "interview_style": campaign.interview_style,
        "difficulty": campaign.difficulty,
        "question_categories": campaign.question_categories,
        "evaluation_criteria": campaign.evaluation_criteria,
        "status": campaign.status,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
    }
    if assigned_student_count is not None:
        result["assigned_student_count"] = assigned_student_count
    return result


def serialize_interview_template(template: InterviewTemplate) -> dict:
    return {
        "id": str(template.id),
        "name": template.name,
        "description": template.description,
        "is_default": template.is_default,
        "rounds": [
            {
                "round_type": r.round_type,
                "sequence_order": r.sequence_order,
                "duration_minutes": r.duration_minutes,
                "question_categories": r.question_categories,
                "evaluation_criteria": r.evaluation_criteria,
                "instructions": r.instructions,
            }
            for r in sorted(template.rounds, key=lambda r: r.sequence_order)
        ],
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }
