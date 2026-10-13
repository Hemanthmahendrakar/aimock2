"""
Gunicorn entrypoint: `gunicorn -c gunicorn.conf.py wsgi:app`
Never use `flask run` / the Flask dev server in production.
"""
from app import create_app

app = create_app()
