"""
Global error handlers so unhandled exceptions never leak stack traces
or internals to clients, and every error follows the same JSON shape.
"""
import logging

from flask import Flask
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.utils.responses import error

logger = logging.getLogger("app.errors")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(e):
        return error("not_found", "Resource not found.", 404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return error("method_not_allowed", "Method not allowed.", 405)

    @app.errorhandler(429)
    def rate_limited(e):
        return error("rate_limited", "Too many requests. Please try again later.", 429)

    @app.errorhandler(ValidationError)
    def validation_error(e):
        return error("validation_error", "Invalid request data.", 422)

    @app.errorhandler(SQLAlchemyError)
    def db_error(e):
        from app.extensions import db

        db.session.rollback()
        logger.exception("Database error")
        return error("internal_error", "A database error occurred.", 500)

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        logger.exception("Unhandled exception")
        return error("internal_error", "An unexpected error occurred.", 500)
