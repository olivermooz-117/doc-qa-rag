import os

import pytest
from sqlalchemy import text

from app import create_app
from models import db


@pytest.fixture(scope="session")
def test_database_url():
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/docqa_test",
    )


@pytest.fixture
def app(test_database_url, monkeypatch):
    """Create an isolated Flask application for each test."""
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    app = create_app()

    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=test_database_url,
    )

    with app.app_context():
        db.session.execute(
            text("CREATE EXTENSION IF NOT EXISTS vector")
        )
        db.session.commit()

        db.drop_all()
        db.create_all()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Return a Flask test client."""
    return app.test_client()

