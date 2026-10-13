"""
Extension instances, created here (uninitialized) and bound to the app
in the application factory. Importing from this module avoids circular
imports between app/__init__.py and the route/service modules.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery import Celery

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
limiter = Limiter(key_func=get_remote_address)

# Created without an app here (tasks import this at module load time to
# register via @celery.task), fully configured by init_celery() inside
# the application factory. Both the real worker process (celery_worker.py)
# and the web process call create_app(), so both end up with the same
# configured instance.
celery = Celery(__name__)


def init_celery(app):
    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        task_always_eager=app.config["CELERY_TASK_ALWAYS_EAGER"],
        task_eager_propagates=app.config["CELERY_TASK_EAGER_PROPAGATES"],
    )

    class ContextTask(celery.Task):
        """Ensures every task runs inside a Flask app context, so
        db.session / current_app work the same as in a request."""

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
