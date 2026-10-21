"""
Flask application factory. Nothing here is module-global-state that
would break multiple app instances (important for tests, which spin up
a fresh app per test session/module).
"""
import logging

from flask import Flask

from app.config.settings import get_config
from app.extensions import db, migrate, cors, limiter, init_celery


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    _init_logging(app)
    _init_sentry(app)
    _init_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)

    return app


def _init_logging(app: Flask) -> None:
    level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _init_sentry(app: Flask) -> None:
    dsn = app.config.get("SENTRY_DSN")
    if not dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[FlaskIntegration()],
        environment=app.config["ENV"],
        traces_sample_rate=0.1,
    )


def _init_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}},
        supports_credentials=True,
    )
    limiter.init_app(app)
    init_celery(app)

    # Import models so SQLAlchemy metadata is populated (needed for
    # migrations / create_all in tests) even though routes don't import
    # them directly at module load time.
    from app import models  # noqa: F401


def _register_blueprints(app: Flask) -> None:
    from app.routes import register_routes

    register_routes(app)


def _register_error_handlers(app: Flask) -> None:
    from app.error_handlers import register_error_handlers

    register_error_handlers(app)
