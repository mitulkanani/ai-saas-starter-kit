from tests.conftest import register


def test_mock_summary_records_usage(client):
    body, headers = register(client)
    org_id = body["organizations"][0]["id"]
    response = client.post("/api/ai/summarize", headers=headers, json={
        "organization_id": org_id,
        "input_text": "This is a longer example paragraph. It can be summarized locally with deterministic behavior.",
        "max_output_tokens": 100,
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["provider"] == "mock"
    assert result["total_tokens"] == result["input_tokens"] + result["output_tokens"]
    assert result["usage_used_tokens"] == result["total_tokens"]
    assert result["estimated_cost_usd"] == 0
    usage = client.get(f"/api/organizations/{org_id}/usage", headers=headers).json()
    assert usage["used_tokens"] == result["total_tokens"]
    assert usage["event_count"] == 1


def test_usage_events_are_scoped_to_organization(client):
    body, headers = register(client)
    org_id = body["organizations"][0]["id"]
    client.post("/api/ai/summarize", headers=headers, json={
        "organization_id": org_id,
        "input_text": "An example text with enough characters for a summary.",
    })
    response = client.get(f"/api/organizations/{org_id}/usage/events", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["operation"] == "summarize"


def test_quota_enforced_before_provider_call(client):
    body, headers = register(client)
    org = body["organizations"][0]
    from app.models import Organization
    # Reconfigure the fixture database only, without touching developer data.
    with client.app.state.test_session_factory() as db:
        db.query(Organization).filter(Organization.id == org["id"]).update({"monthly_token_limit": 1})
        db.commit()
    response = client.post("/api/ai/summarize", headers=headers, json={
        "organization_id": org["id"],
        "input_text": "This request requires more tokens than the small configured workspace limit.",
        "max_output_tokens": 100,
    })
    assert response.status_code == 429
    usage = client.get(f"/api/organizations/{org['id']}/usage", headers=headers).json()
    assert usage["used_tokens"] == 0


def test_invalid_summary_request_is_rejected(client):
    _, headers = register(client)
    response = client.post("/api/ai/summarize", headers=headers, json={
        "organization_id": "not-a-uuid", "input_text": "short",
    })
    assert response.status_code == 422


def test_failed_provider_releases_reserved_tokens(client, monkeypatch):
    body, headers = register(client)
    org_id = body["organizations"][0]["id"]
    import app.routes as routes
    from app.services.ai import AIProviderError

    def fail_generation(*args, **kwargs):
        raise AIProviderError("provider unavailable")

    monkeypatch.setattr(routes, "generate_summary", fail_generation)
    response = client.post("/api/ai/summarize", headers=headers, json={
        "organization_id": org_id,
        "input_text": "This request should reserve tokens and then release them after failure.",
    })
    assert response.status_code == 503
    usage = client.get(f"/api/organizations/{org_id}/usage", headers=headers).json()
    assert usage["used_tokens"] == 0
    assert usage["event_count"] == 0


def test_new_workspace_is_owned_and_isolated(client):
    _, headers = register(client)
    response = client.post("/api/organizations", headers=headers, json={"name": "Second Team"})
    assert response.status_code == 201
    assert response.json()["role"] == "owner"
    orgs = client.get("/api/organizations", headers=headers).json()
    assert {org["name"] for org in orgs} == {"Acme Workspace", "Second Team"}
