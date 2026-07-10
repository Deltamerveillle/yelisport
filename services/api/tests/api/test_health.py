from fastapi.testclient import TestClient


def test_health_returns_service_metadata(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request"
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "api"
    assert response.json()["environment"] == "test"
