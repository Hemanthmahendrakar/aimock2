import os

import pytest

os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("COOKIE_SECURE", "false")

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    application = create_app("testing")
    with application.app_context():
        yield application


@pytest.fixture(autouse=True)
def db_setup(app):
    """
    Fresh schema per test. Simpler and safer than SAVEPOINT-based
    rollback here because the service layer calls db.session.commit()
    itself (real transactions, matching production behavior).
    """
    with app.app_context():
        _db.create_all()
        yield
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def register_payload():
    return {
        "institute_name": "Test Institute",
        "institute_email": "admissions@test-institute.example",
        "admin_full_name": "Ada Admin",
        "admin_email": "ada@test-institute.example",
        "password": "SuperSecret123",
    }
