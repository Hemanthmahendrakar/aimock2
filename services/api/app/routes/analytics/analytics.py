"""
Institute analytics routes. institute_id always comes from
g.current_institute_id — filters (campaign_id, department, batch,
role, dates) narrow which of THAT institute's own data is aggregated;
they never select a different institute's data.
"""
from flask import Blueprint, request, g
from pydantic import ValidationError

from app.models import RoleName
from app.schemas.analytics_schemas import AnalyticsQuery
from app.services.analytics_service import AnalyticsService
from app.utils.authorization import require_auth, require_role, require_institute_scope
from app.utils.responses import ok, error

bp = Blueprint("analytics", __name__, url_prefix="/api/v1/institute/analytics")


def _validation_error_response(exc: ValidationError):
    details = [
        {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return error("validation_error", "Invalid query parameters.", 422, details=details)


@bp.get("")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def get_dashboard():
    try:
        query = AnalyticsQuery.model_validate(dict(request.args))
    except ValidationError as exc:
        return _validation_error_response(exc)

    dashboard = AnalyticsService().get_dashboard(
        g.current_institute_id, query=query.model_dump()
    )
    return ok(dashboard)


@bp.get("/filter-options")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def get_filter_options():
    options = AnalyticsService().filter_options(g.current_institute_id)
    return ok(options)
