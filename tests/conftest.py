import os

# Must be set before any app imports so scheduler never starts during tests
os.environ["SCHEDULER_ENABLED"] = "false"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.storage.postgres as _pg
from app.storage.models import Base


@pytest.fixture(scope="session")
def in_memory_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    original_engine = _pg.engine
    original_session = _pg.SessionLocal
    _pg.engine = engine
    _pg.SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    yield engine

    _pg.engine = original_engine
    _pg.SessionLocal = original_session
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="session")
def api_client(in_memory_engine):
    from fastapi.testclient import TestClient

    from app.api.main import app
    from app.storage.postgres import get_session

    TestSession = sessionmaker(bind=in_memory_engine, autoflush=False, expire_on_commit=False)

    def override_session():
        with TestSession() as s:
            yield s

    app.dependency_overrides[get_session] = override_session

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
