from tests.conftest import register


def test_users_only_see_their_own_organizations(client):
    first, first_headers = register(client, "first@example.com", "First Co")
    second, second_headers = register(client, "second@example.com", "Second Co")
    first_org = first["organizations"][0]["id"]
    second_org = second["organizations"][0]["id"]
    assert [o["id"] for o in client.get("/api/organizations", headers=first_headers).json()] == [first_org]
    assert [o["id"] for o in client.get("/api/organizations", headers=second_headers).json()] == [second_org]
    response = client.get(f"/api/organizations/{first_org}/usage", headers=second_headers)
    assert response.status_code == 404


def test_cannot_run_ai_against_another_tenant(client):
    first, first_headers = register(client, "first@example.com", "First Co")
    _, second_headers = register(client, "second@example.com", "Second Co")
    org_id = first["organizations"][0]["id"]
    response = client.post("/api/ai/summarize", headers=second_headers, json={
        "organization_id": org_id,
        "input_text": "This is sufficiently long text to summarize safely.",
    })
    assert response.status_code == 404
