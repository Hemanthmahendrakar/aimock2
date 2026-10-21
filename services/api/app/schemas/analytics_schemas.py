"""
Query-param validation for GET /api/v1/institute/analytics. A plain
BaseModel rather than parsing query args ad hoc in the route, matching
how every other list/filter endpoint in this app validates input.
"""
from datetime import datetime

from pydantic import BaseModel, field_validator


class AnalyticsQuery(BaseModel):
    campaign_id: str | None = None
    department: str | None = None
    batch: str | None = None
    role: str | None = None
    date_from: str | None = None
    date_to: str | None = None

    @field_validator("date_from", "date_to")
    @classmethod
    def valid_iso_date(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            datetime.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("Must be an ISO 8601 date, e.g. 2026-01-01.") from exc
        return v
