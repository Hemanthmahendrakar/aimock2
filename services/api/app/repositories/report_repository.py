import uuid
from typing import Optional

from app.extensions import db
from app.models import Report, ReportVersion


class ReportRepository:
    def get_by_interview(self, interview_id: uuid.UUID) -> Optional[Report]:
        return db.session.query(Report).filter(Report.interview_id == interview_id).first()

    def get_by_interview_scoped(
        self, interview_id: uuid.UUID, *, institute_id: uuid.UUID
    ) -> Optional[Report]:
        return (
            db.session.query(Report)
            .filter(Report.interview_id == interview_id, Report.institute_id == institute_id)
            .first()
        )

    def create(self, report: Report) -> Report:
        db.session.add(report)
        db.session.flush()
        return report

    def save(self, report: Report) -> Report:
        db.session.add(report)
        db.session.flush()
        return report

    def next_version_number(self, report_id: uuid.UUID) -> int:
        latest = (
            db.session.query(ReportVersion)
            .filter(ReportVersion.report_id == report_id)
            .order_by(ReportVersion.version_number.desc())
            .first()
        )
        return (latest.version_number + 1) if latest else 1

    def create_version(self, version: ReportVersion) -> ReportVersion:
        db.session.add(version)
        db.session.flush()
        return version
