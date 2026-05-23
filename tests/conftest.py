# tests/conftest.py
# Shared fixtures for all Spendly test modules.
#
# DB isolation strategy: monkeypatch database.db.DB_PATH to a tmp_path
# throwaway file so no test ever reads from or writes to the committed
# spendly.db. Each test that uses the `app` fixture gets its own
# private SQLite file that pytest deletes after the session.

import importlib

import pytest

from database import db as db_module


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Flask app wired to an isolated, throwaway SQLite file.

    The monkeypatch replaces DB_PATH before the module-level
    init_db() / seed_db() block inside app.py is re-executed via
    importlib.reload(), so every helper that calls get_db() inside
    this test session uses the temp file, never spendly.db.
    """
    test_db = tmp_path / "test_spendly.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(test_db))

    import app as app_module
    importlib.reload(app_module)
    flask_app = app_module.app
    flask_app.config.update({"TESTING": True})

    with flask_app.app_context():
        db_module.init_db()

    yield flask_app


@pytest.fixture()
def client(app):
    """Unauthenticated test client."""
    return app.test_client()


@pytest.fixture()
def seeded_app(app):
    """App with the standard 8-expense demo dataset loaded.

    seed_db() is idempotent — it checks row_count > 0 before inserting,
    so calling it once here is safe.
    """
    with app.app_context():
        db_module.seed_db()
    return app


@pytest.fixture()
def seeded_client(seeded_app):
    """Unauthenticated test client against the seeded DB."""
    return seeded_app.test_client()


@pytest.fixture()
def logged_in_client(seeded_app):
    """Authenticated test client for the seeded demo user (id=1).

    Session is set directly via session_transaction() to avoid depending
    on the login route being exercised. Session keys must match what
    app.py stores: 'user_id' and 'user_name'.
    """
    client = seeded_app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = "Demo User"
    return client
