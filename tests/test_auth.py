from tests.conftest import register


def test_register_creates_user_and_owner_organization(client):
    body, headers = register(client)
    assert body["user"]["email"] == "owner@example.com"
    assert len(body["access_token"]) > 20
    assert body["organizations"][0]["role"] == "owner"
    assert client.get("/api/me", headers=headers).json()["email"] == "owner@example.com"


def test_login_returns_token(client):
    register(client)
    response = client.post("/api/auth/login", json={
        "email": "OWNER@example.com", "password": "correct-horse-battery"
    })
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "owner@example.com"


def test_invalid_password_is_rejected(client):
    register(client)
    response = client.post("/api/auth/login", json={
        "email": "owner@example.com", "password": "wrong"
    })
    assert response.status_code == 401


def test_duplicate_email_is_rejected_case_insensitively(client):
    register(client)
    response = client.post("/api/auth/register", json={
        "email": "OWNER@example.com", "password": "correct-horse-battery",
        "organization_name": "Second Workspace",
    })
    assert response.status_code == 409


def test_weak_password_and_extra_fields_are_rejected(client):
    response = client.post("/api/auth/register", json={
        "email": "owner@example.com", "password": "short", 
        "organization_name": "Acme", "admin": True,
    })
    assert response.status_code == 422


def test_api_requires_authentication(client):
    assert client.get("/api/organizations").status_code == 401
