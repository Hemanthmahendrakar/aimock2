import multiprocessing
import os

bind = f"0.0.0.0:{os.environ.get('PORT', 8000)}"
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "gevent"
timeout = 60
accesslog = "-"
errorlog = "-"
