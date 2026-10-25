"""CORS contract for the public SMS24 Cloudflare Pages experience."""

from fastapi.testclient import TestClient


def test_cloudflare_production_and_preview_origins_are_allowed(client: TestClient) -> None:
    for origin in (
        "https://sms24-web.pages.dev",
        "https://sms24-demo-20261025.sms24-web.pages.dev",
        "https://new-preview.sms24-web.pages.dev",
    ):
        response = client.options(
            "/api/v1/sports",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"


def test_unrelated_or_spoofed_pages_origins_are_not_allowed(client: TestClient) -> None:
    for origin in (
        "https://attacker.pages.dev",
        "https://sms24-web.pages.dev.attacker.example",
        "https://attacker.sms24-web.pages.dev.attacker.example",
        "http://sms24-web.pages.dev",
    ):
        response = client.options(
            "/api/v1/sports",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
