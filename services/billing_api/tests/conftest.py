"""Test fixtures: in-memory SQLite + seed data, no Docker, cloud or LLM needed."""

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import seed as seed_module
from app.db import Base, get_db
from app.main import app


@pytest.fixture
def db_session(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # Fast bcrypt for tests only.
    monkeypatch.setattr(
        seed_module, "hash_password", lambda p: bcrypt.hashpw(p.encode(), bcrypt.gensalt(rounds=4)).decode()
    )
    with TestingSession() as s:
        seed_module.seed(s)

    def _override():
        with TestingSession() as s:
            yield s

    app.dependency_overrides[get_db] = _override
    yield TestingSession
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def client(db_session):
    return TestClient(app)


def _login(client, subscriber_no, password):
    resp = client.post("/api/v1/auth/login", json={"subscriberNo": subscriber_no, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


@pytest.fixture
def admin_headers(client):
    return _login(client, "ADMIN001", "Admin#2026")


@pytest.fixture
def user1_headers(client):
    return _login(client, "5551001", "Demo#1001")


@pytest.fixture
def user2_headers(client):
    return _login(client, "5551002", "Demo#1002")
