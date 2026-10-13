"""Tenant-scoped institute dashboard summary."""
from flask import Blueprint, g

from app.extensions import db
from app.models import (
    Campaign, CampaignStatus, Interview, InterviewStatus, Report, Student,
)
from app.models import RoleName
from app.utils.authorization import require_auth, require_institute_scope, require_role
from app.utils.responses import ok

bp = Blueprint("institute_dashboard", __name__, url_prefix="/api/v1/institute")


@bp.get("/dashboard")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def dashboard():
    # The tenant ID comes only from the verified auth context. Never accept it
    # from query parameters or request payloads.
    institute_id = g.current_institute_id

    students_query = Student.query.filter(
        Student.institute_id == institute_id, Student.deleted_at.is_(None)
    )
    campaigns_query = Campaign.query.filter(
        Campaign.institute_id == institute_id, Campaign.deleted_at.is_(None)
    )
    interviews_query = Interview.query.filter(Interview.institute_id == institute_id)

    total_students = students_query.count()
    total_campaigns = campaigns_query.count()
    active_campaigns = campaigns_query.filter(
        Campaign.status == CampaignStatus.ACTIVE
    ).count()
    assigned_interviews = interviews_query.count()
    completed_interviews = interviews_query.filter(
        Interview.completed_at.isnot(None)
    ).count()
    reports_ready = Report.query.filter(Report.institute_id == institute_id).count()

    recent_campaigns = (
        campaigns_query.order_by(Campaign.created_at.desc()).limit(5).all()
    )

    return ok({
        "institute_id": str(institute_id),
        "stats": {
            "total_students": total_students,
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "assigned_interviews": assigned_interviews,
            "completed_interviews": completed_interviews,
            "reports_ready": reports_ready,
            "completion_rate": round(completed_interviews / assigned_interviews * 100, 1)
                if assigned_interviews else 0.0,
        },
        "recent_campaigns": [
            {
                "id": str(campaign.id),
                "name": campaign.name,
                "role": campaign.role,
                "status": campaign.status,
                "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
            }
            for campaign in recent_campaigns
        ],
    })
