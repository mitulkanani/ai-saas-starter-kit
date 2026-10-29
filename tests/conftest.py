import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import app
import app.services.ai as ai_service


@pytest.fixture()
def client(monkeypatch):
    # Isolated in-memory database shared by all test sessions.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.test_session_factory = TestingSessionLocal
    monkeypatch.setenv("AI_PROVIDER", "mock")
    from dataclasses import replace
    monkeypatch.setattr(ai_service, "settings", replace(settings, ai_provider="mock", openai_api_key=None))
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    test_engine.dispose()


def register(client, email="owner@example.com", organization_name="Acme Workspace"):
    response = client.post("/api/auth/register", json={
        "email": email,
        "password": "correct-horse-battery",
        "organization_name": organization_name,
    })
    assert response.status_code == 201, response.text
    body = response.json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    return body, headers
