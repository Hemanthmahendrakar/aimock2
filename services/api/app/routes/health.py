from flask import Blueprint

from app.utils.responses import ok

bp = Blueprint("health", __name__, url_prefix="/api/v1")


@bp.get("/health")
def health():
    return ok({"status": "ok"})
