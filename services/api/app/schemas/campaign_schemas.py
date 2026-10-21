from pydantic import BaseModel, Field, field_validator


class CreateCampaignRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    role: str = Field(min_length=1, max_length=255)
    experience_level: str | None = Field(default=None, max_length=64)
    department: str | None = Field(default=None, max_length=128)
    batch: str | None = Field(default=None, max_length=32)
    company_id: str | None = None
    campus_id: str | None = None
    job_description: str | None = Field(default=None, max_length=12000)
    question_source: str | None = "ai"

    # If set, CampaignService copies this template's round config in as
    # defaults for any field below the caller doesn't explicitly set.
    interview_template_id: str | None = None

    technical_duration_minutes: int | None = Field(default=None, gt=0, le=180)
    managerial_duration_minutes: int | None = Field(default=None, gt=0, le=180)
    hr_duration_minutes: int | None = Field(default=None, gt=0, le=180)

    technical_instructions: str | None = Field(default=None, max_length=4000)
    managerial_instructions: str | None = Field(default=None, max_length=4000)
    hr_instructions: str | None = Field(default=None, max_length=4000)

    interviewer_avatar: str | None = Field(default=None, max_length=128)
    interviewer_voice: str | None = Field(default=None, max_length=128)
    interview_style: str | None = Field(default=None, max_length=64)

    difficulty: str | None = None
    question_categories: list[str] | None = None
    evaluation_criteria: dict | None = None


class UpdateCampaignRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    role: str | None = Field(default=None, min_length=1, max_length=255)
    experience_level: str | None = Field(default=None, max_length=64)
    department: str | None = Field(default=None, max_length=128)
    batch: str | None = Field(default=None, max_length=32)
    company_id: str | None = None
    campus_id: str | None = None
    job_description: str | None = Field(default=None, max_length=12000)
    question_source: str | None = None

    technical_duration_minutes: int | None = Field(default=None, gt=0, le=180)
    managerial_duration_minutes: int | None = Field(default=None, gt=0, le=180)
    hr_duration_minutes: int | None = Field(default=None, gt=0, le=180)

    technical_instructions: str | None = Field(default=None, max_length=4000)
    managerial_instructions: str | None = Field(default=None, max_length=4000)
    hr_instructions: str | None = Field(default=None, max_length=4000)

    interviewer_avatar: str | None = Field(default=None, max_length=128)
    interviewer_voice: str | None = Field(default=None, max_length=128)
    interview_style: str | None = Field(default=None, max_length=64)

    difficulty: str | None = None
    question_categories: list[str] | None = None
    evaluation_criteria: dict | None = None


class AssignStudentsRequest(BaseModel):
    student_ids: list[str] = Field(min_length=1, max_length=500)

    @field_validator("student_ids")
    @classmethod
    def dedupe(cls, v: list[str]) -> list[str]:
        # Preserve order while removing duplicates from the request itself.
        seen = set()
        result = []
        for sid in v:
            if sid not in seen:
                seen.add(sid)
                result.append(sid)
        return result
