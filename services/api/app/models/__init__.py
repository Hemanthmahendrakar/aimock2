"""
Import every model here so that:
  - `from app.models import User, Institute, ...` works app-wide
  - Alembic's `--autogenerate` sees the full metadata
"""
from app.models.institute import Institute, InstituteStatus, BrandingField
from app.models.role import Role, RoleName, UserRole
from app.models.user import User, UserStatus
from app.models.auth_tokens import (
    RefreshToken,
    EmailVerificationToken,
    PasswordResetToken,
)
from app.models.audit_log import AuditLog
from app.models.student import Student, StudentStatus
from app.models.campaign import Campaign, CampaignStatus, CampaignDifficulty, CampaignStudent
from app.models.interview_template import (
    InterviewTemplate,
    InterviewTemplateRound,
    InterviewRoundType,
)
from app.models.resume import Resume, ResumeVersion, CandidateProfile, ProcessingStatus
from app.models.interview import (
    Interview,
    InterviewStatus,
    RoundStatus,
    InterviewRound,
    InterviewQuestion,
    InterviewAnswer,
)
from app.models.evaluation import Evaluation, EvaluationDimension
from app.models.report import Report, ReportVersion
from app.models.campus import Campus
from app.models.company import Company
from app.models.question_bank import QuestionBankQuestion

__all__ = [
    "Institute",
    "InstituteStatus",
    "BrandingField",
    "Role",
    "RoleName",
    "UserRole",
    "User",
    "UserStatus",
    "RefreshToken",
    "EmailVerificationToken",
    "PasswordResetToken",
    "AuditLog",
    "Student",
    "StudentStatus",
    "Campaign",
    "CampaignStatus",
    "CampaignDifficulty",
    "CampaignStudent",
    "InterviewTemplate",
    "InterviewTemplateRound",
    "InterviewRoundType",
    "Resume",
    "ResumeVersion",
    "CandidateProfile",
    "ProcessingStatus",
    "Interview",
    "InterviewStatus",
    "RoundStatus",
    "InterviewRound",
    "InterviewQuestion",
    "InterviewAnswer",
    "Evaluation",
    "EvaluationDimension",
    "Report",
    "ReportVersion",
    "Campus",
    "Company",
    "QuestionBankQuestion",
]
