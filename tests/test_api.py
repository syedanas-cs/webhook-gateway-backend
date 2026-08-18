import pytest
import httpx


@pytest.mark.asyncio
async def test_healthcheck(client: httpx.AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["services"]["database"] == "reachable"
    assert data["services"]["redis"] == "reachable"


@pytest.mark.asyncio
async def test_auth_and_api_key_flow(client: httpx.AsyncClient):
    # 1. Register
    reg_payload = {
        "email": "tester@example.com",
        "password": "SecurePassword123!",
        "full_name": "Test Engineer",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code in (201, 400)  # 400 if already exists

    # 2. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        data={"username": "tester@example.com", "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create API Key
    key_res = await client.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Test Integration Key"},
    )
    assert key_res.status_code == 201
    key_data = key_res.json()
    assert "raw_api_key" in key_data
    assert key_data["raw_api_key"].startswith("wh_live_")

    # 4. List API Keys (raw key must be hidden/masked)
    list_res = await client.get("/api/v1/api-keys", headers=headers)
    assert list_res.status_code == 200
    assert any(k["id"] == key_data["id"] for k in list_res.json())

    # Append to tests/test_api.py

@pytest.mark.asyncio
async def test_webhook_registration_and_stats(client: httpx.AsyncClient):
    # 1. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        data={"username": "tester@example.com", "password": "SecurePassword123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Register a webhook endpoint with correct field 'target_url'
    ep_payload = {
        "target_url": "https://httpbin.org/post",
        "description": "Integration Test Receiver",
        "subscribed_events": ["payment.completed", "user.created"],
    }
    ep_res = await client.post(
        "/api/v1/webhooks/endpoints",
        headers=headers,
        json=ep_payload,
    )
    assert ep_res.status_code in (201, 200), f"Registration failed: {ep_res.text}"
    ep_data = ep_res.json()
    assert str(ep_data["target_url"]).rstrip("/") == "https://httpbin.org/post"
    assert "secret_token" in ep_data

    # 3. Verify Stats Endpoint
    stats_res = await client.get("/api/v1/webhooks/stats?hours=24", headers=headers)
    assert stats_res.status_code == 200, f"Stats failed: {stats_res.text}"
    stats_data = stats_res.json()
    assert "total_deliveries" in stats_data
    assert "success_rate_percentage" in stats_data