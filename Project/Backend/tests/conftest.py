"""Test fixtures.

Every test runs against a throwaway SQLite file, never the developer's real
`insta_automate.db`. DATABASE_URL is set before backend.database is imported,
because the engine is created at module import time.
"""
import os
import tempfile
import uuid

import pytest

os.environ.setdefault("ENVIRONMENT", "development")
_TEST_DB = os.path.join(tempfile.gettempdir(), f"lyvora_test_{uuid.uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["ADMIN_INITIAL_PASSWORD"] = "test-admin-password"


@pytest.fixture(scope="session", autouse=True)
def _database():
    from backend.database import init_db

    init_db()
    yield
    from backend.database import engine

    engine.dispose()
    try:
        os.remove(_TEST_DB)
    except OSError:
        pass


@pytest.fixture
def db():
    from backend.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def workspaces(db):
    """Two independent tenants, as two different customers would be."""
    from backend.database import Workspace

    created = []
    for name in ("Tenant A", "Tenant B"):
        slug = f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        workspace = Workspace(name=name, slug=slug)
        db.add(workspace)
        created.append(workspace)
    db.commit()
    for workspace in created:
        db.refresh(workspace)
    yield created
    for workspace in created:
        db.delete(workspace)
    db.commit()
