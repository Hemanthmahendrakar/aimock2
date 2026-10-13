"""
Analytics data access. Two separate query paths, deliberately not one:

- Interview-level counts (total/started/completed) are meaningful for
  EVERY interview in scope, whether or not it has a report yet.
- Score-based metrics only exist for interviews that reached
  report_ready — querying ReportVersion directly (via its owning
  Report) rather than trying to force one mega-query to serve both.

Both paths share the same filter set (campaign/department/batch/role/
date range), applied via the same joins, so a dashboard filter always
means the same thing regardless of which metric it's shaping.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.extensions import db
from app.models import Interview, Campaign, Student, Report, ReportVersion


@dataclass
class AnalyticsFilters:
    campaign_id: Optional[uuid.UUID] = None
    department: Optional[str] = None
    batch: Optional[str] = None
    role: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class AnalyticsRepository:
    def _apply_filters(self, query, filters: AnalyticsFilters):
        if filters.campaign_id is not None:
            query = query.filter(Interview.campaign_id == filters.campaign_id)
        if filters.department:
            query = query.filter(Student.department == filters.department)
        if filters.batch:
            query = query.filter(Student.batch == filters.batch)
        if filters.role:
            query = query.filter(Campaign.role == filters.role)
        if filters.date_from is not None:
            query = query.filter(Interview.created_at >= filters.date_from)
        if filters.date_to is not None:
            query = query.filter(Interview.created_at <= filters.date_to)
        return query

    def list_interviews(
        self, institute_id: uuid.UUID, filters: AnalyticsFilters
    ) -> list[Interview]:
        query = (
            db.session.query(Interview)
            .join(Campaign, Campaign.id == Interview.campaign_id)
            .join(Student, Student.id == Interview.student_id)
            .filter(Interview.institute_id == institute_id)
        )
        query = self._apply_filters(query, filters)
        return query.all()

    def list_report_versions(
        self, institute_id: uuid.UUID, filters: AnalyticsFilters
    ) -> list[tuple[ReportVersion, Student]]:
        """
        Returns (ReportVersion, Student) pairs — the student is needed
        alongside the score for department/batch breakdowns, and
        fetching it here avoids an N+1 lookup per report in the
        service layer.
        """
        query = (
            db.session.query(ReportVersion, Student)
            .join(Report, Report.id == ReportVersion.report_id)
            .join(Interview, Interview.id == Report.interview_id)
            .join(Campaign, Campaign.id == Interview.campaign_id)
            .join(Student, Student.id == Interview.student_id)
            .filter(
                Interview.institute_id == institute_id,
                Report.current_version_id == ReportVersion.id,
            )
        )
        query = self._apply_filters(query, filters)
        return query.all()

    def count_students(
        self, institute_id: uuid.UUID, *, department: Optional[str], batch: Optional[str]
    ) -> int:
        query = db.session.query(Student).filter(
            Student.institute_id == institute_id, Student.deleted_at.is_(None)
        )
        if department:
            query = query.filter(Student.department == department)
        if batch:
            query = query.filter(Student.batch == batch)
        return query.count()

    def distinct_departments(self, institute_id: uuid.UUID) -> list[str]:
        rows = (
            db.session.query(Student.department)
            .filter(
                Student.institute_id == institute_id,
                Student.department.isnot(None),
                Student.deleted_at.is_(None),
            )
            .distinct()
            .all()
        )
        return sorted(r[0] for r in rows if r[0])

    def distinct_batches(self, institute_id: uuid.UUID) -> list[str]:
        rows = (
            db.session.query(Student.batch)
            .filter(
                Student.institute_id == institute_id,
                Student.batch.isnot(None),
                Student.deleted_at.is_(None),
            )
            .distinct()
            .all()
        )
        return sorted(r[0] for r in rows if r[0])
