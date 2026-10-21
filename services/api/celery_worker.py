"""
Celery worker entrypoint: `celery -A celery_worker.celery worker --loglevel=info`

Creating the Flask app here (same factory the web process uses) runs
init_celery(app), which configures the shared `celery` instance from
app.extensions with this process's config. Importing the task modules
below is what actually registers their @celery.task-decorated functions
against that instance — without the import, the worker would start but
never recognize the task names.
"""
from app import create_app
from app.extensions import celery

flask_app = create_app()

from app.tasks import resume_tasks  # noqa: E402, F401
from app.tasks import evaluation_tasks  # noqa: E402, F401
from app.tasks import report_tasks  # noqa: E402, F401
