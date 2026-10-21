"""
Institute analytics aggregation. All aggregation happens in Python
after fetching filtered rows, not via SQL GROUP BY — reasonable for a
per-institute dashboard at the data volumes this app deals with
(students/interviews for one institute, not a cross-tenant warehouse).
Worth revisiting with real SQL aggregates if an institute's interview
volume gets very large.
"""
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional

from app.models import InterviewStatus
from app.repositories.analytics_repository import AnalyticsRepository, AnalyticsFilters

# Readiness bands are an invented, documented scheme — the spec asks
# for a "readiness distribution" without defining the bands.
READINESS_BANDS = [
    ("needs_improvement", 0, 49),
    ("developing", 50, 69),
    ("ready", 70, 84),
    ("excellent", 85, 100),
]

# Interview statuses that mean "the student actually started the
# interview" — anything past the lobby.
_STARTED_STATUSES = {
    InterviewStatus.IN_PROGRESS, InterviewStatus.COMPLETED, InterviewStatus.EVALUATING,
    InterviewStatus.REPORT_GENERATING, InterviewStatus.REPORT_READY, InterviewStatus.FAILED,
}
# "Completed" here means the interview itself finished (all rounds
# answered/timed out) — interview.completed_at is set — regardless of
# whether evaluation/report generation succeeded afterward.

MAX_SKILL_GAPS_RETURNED = 10


def _readiness_band(score: int) -> str:
    for name, low, high in READINESS_BANDS:
        if low <= score <= high:
            return name
    return READINESS_BANDS[-1][0]


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    return datetime.fromisoformat(raw)


class AnalyticsService:
    def __init__(self):
        self.analytics = AnalyticsRepository()

    def get_dashboard(self, institute_id: uuid.UUID, *, query: dict) -> dict:
        filters = AnalyticsFilters(
            campaign_id=uuid.UUID(query["campaign_id"]) if query.get("campaign_id") else None,
            department=query.get("department") or None,
            batch=query.get("batch") or None,
            role=query.get("role") or None,
            date_from=_parse_date(query.get("date_from")),
            date_to=_parse_date(query.get("date_to")),
        )

        interviews = self.analytics.list_interviews(institute_id, filters)
        report_rows = self.analytics.list_report_versions(institute_id, filters)

        total_students = self.analytics.count_students(
            institute_id, department=filters.department, batch=filters.batch
        )

        assigned = len(interviews)
        started = sum(1 for iv in interviews if iv.status in _STARTED_STATUSES)
        completed = sum(1 for iv in interviews if iv.completed_at is not None)
        completion_rate = round(completed / assigned * 100, 1) if assigned else 0.0

        scores = [rv.overall_score for rv, _ in report_rows]
        score_stats = {
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "highest_score": max(scores) if scores else None,
            "lowest_score": min(scores) if scores else None,
            "scored_interviews": len(scores),
        }

        dimension_performance = {
            "technical": self._avg([rv.technical_score for rv, _ in report_rows]),
            "communication": self._avg([rv.communication_score for rv, _ in report_rows]),
            "managerial": self._avg([rv.managerial_score for rv, _ in report_rows]),
            "hr": self._avg([rv.hr_score for rv, _ in report_rows]),
        }

        readiness_distribution = {name: 0 for name, _, _ in READINESS_BANDS}
        for rv, _ in report_rows:
            readiness_distribution[_readiness_band(rv.overall_score)] += 1

        department_performance = self._group_avg_score(
            report_rows, key=lambda student: student.department
        )
        batch_performance = self._group_avg_score(
            report_rows, key=lambda student: student.batch
        )

        skill_gap_counts: Counter[str] = Counter()
        for rv, _ in report_rows:
            for gap in rv.technical_skill_gaps:
                skill_gap_counts[gap.strip()] += 1
        skill_gaps = [
            {"gap": gap, "count": count}
            for gap, count in skill_gap_counts.most_common(MAX_SKILL_GAPS_RETURNED)
        ]

        return {
            "filters_applied": {
                "campaign_id": query.get("campaign_id"),
                "department": filters.department,
                "batch": filters.batch,
                "role": filters.role,
                "date_from": query.get("date_from"),
                "date_to": query.get("date_to"),
            },
            "total_students": total_students,
            "assigned_interviews": assigned,
            "started_interviews": started,
            "completed_interviews": completed,
            "completion_rate": completion_rate,
            **score_stats,
            "dimension_performance": dimension_performance,
            "readiness_distribution": readiness_distribution,
            "department_performance": department_performance,
            "batch_performance": batch_performance,
            "skill_gaps": skill_gaps,
        }

    def _avg(self, values: list[int]) -> Optional[float]:
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 1) if values else None

    def _group_avg_score(self, report_rows, *, key) -> list[dict]:
        groups: dict[str, list[int]] = defaultdict(list)
        for rv, student in report_rows:
            group_key = key(student)
            if group_key:
                groups[group_key].append(rv.overall_score)
        return sorted(
            (
                {
                    "name": name,
                    "average_score": round(sum(scores) / len(scores), 1),
                    "count": len(scores),
                }
                for name, scores in groups.items()
            ),
            key=lambda row: row["name"],
        )

    def filter_options(self, institute_id: uuid.UUID) -> dict:
        return {
            "departments": self.analytics.distinct_departments(institute_id),
            "batches": self.analytics.distinct_batches(institute_id),
        }
