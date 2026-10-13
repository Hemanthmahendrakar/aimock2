"""
Schemas for interview template CRUD. Rounds are validated as a list of
per-round configs — round_type must be one of technical/managerial/hr
and each type can appear at most once per request (checked in the
service, since Pydantic validators here only see this one request, not
what's already in the DB).
"""
from pydantic import BaseModel, Field, field_validator

from app.models import InterviewRoundType


class RoundConfig(BaseModel):
    round_type: str
    duration_minutes: int = Field(gt=0, le=180)
    question_categories: list[str] = Field(default_factory=list)
    evaluation_criteria: dict = Field(default_factory=dict)
    instructions: str | None = Field(default=None, max_length=4000)

    @field_validator("round_type")
    @classmethod
    def valid_round_type(cls, v: str) -> str:
        if v not in InterviewRoundType.ALL:
            raise ValueError(
                f"round_type must be one of {', '.join(InterviewRoundType.ALL)}."
            )
        return v


class CreateInterviewTemplateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_default: bool = False
    rounds: list[RoundConfig] = Field(default_factory=list, max_length=3)

    @field_validator("rounds")
    @classmethod
    def unique_round_types(cls, v: list[RoundConfig]) -> list[RoundConfig]:
        types = [r.round_type for r in v]
        if len(types) != len(set(types)):
            raise ValueError("Each round type may appear at most once.")
        return v


class UpdateInterviewTemplateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    is_default: bool | None = None
    rounds: list[RoundConfig] | None = Field(default=None, max_length=3)

    @field_validator("rounds")
    @classmethod
    def unique_round_types(cls, v: list[RoundConfig] | None) -> list[RoundConfig] | None:
        if v is None:
            return v
        types = [r.round_type for r in v]
        if len(types) != len(set(types)):
            raise ValueError("Each round type may appear at most once.")
        return v
