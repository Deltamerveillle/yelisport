from fastapi.testclient import TestClient


def test_health_returns_ai_service_status(client: TestClient) -> None:
    response = client.get("/ai/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "ai"
    assert response.json()["environment"] == "test"
