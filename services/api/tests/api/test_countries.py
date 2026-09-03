import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.schemas.auth import AuthUser
from app.services.country_service import CountryService


USER_ID = uuid.UUID("28bbf25e-8d42-4a0a-8bc8-0f41be0fc114")
CI_ID = uuid.UUID("12d66c6f-f5c7-4f17-a42b-a7933572320d")


def country_object(
    *,
    country_id: uuid.UUID = CI_ID,
    iso2: str = "CI",
    iso3: str = "CIV",
    name: str = "Côte d'Ivoire",
    continent_code: str = "AF",
):
    now = datetime.now(UTC)

    return SimpleNamespace(
        id=country_id,
        iso2=iso2,
        iso3=iso3,
        name=name,
        continent_code=continent_code,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def country_dependencies(client: TestClient):
    async def override_current_user():
        return AuthUser(
            id=str(USER_ID),
            email="athlete@example.com",
        )

    async def override_db():
        yield SimpleNamespace()

    client.app.dependency_overrides[get_current_user] = override_current_user
    client.app.dependency_overrides[get_db_session] = override_db

    yield

    client.app.dependency_overrides.clear()


def test_list_african_countries(
    client: TestClient,
    country_dependencies,
    monkeypatch,
) -> None:
    captured = {}

    async def fake_list(
        self,
        *,
        continent_code=None,
        search=None,
    ):
        captured["continent_code"] = continent_code
        captured["search"] = search
        return [country_object()]

    monkeypatch.setattr(
        CountryService,
        "list_countries",
        fake_list,
    )

    response = client.get(
        "/api/v1/countries?continent_code=AF",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["iso2"] == "CI"
    assert response.json()[0]["continent_code"] == "AF"
    assert captured["continent_code"] == "AF"
    assert captured["search"] is None


def test_country_search(
    client: TestClient,
    country_dependencies,
    monkeypatch,
) -> None:
    captured = {}

    async def fake_list(
        self,
        *,
        continent_code=None,
        search=None,
    ):
        captured["continent_code"] = continent_code
        captured["search"] = search
        return [country_object()]

    monkeypatch.setattr(
        CountryService,
        "list_countries",
        fake_list,
    )

    response = client.get(
        "/api/v1/countries?search=ivoire",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert captured["search"] == "ivoire"


def test_get_country_by_iso2(
    client: TestClient,
    country_dependencies,
    monkeypatch,
) -> None:
    captured = {}

    async def fake_get(self, iso2):
        captured["iso2"] = iso2
        return country_object()

    monkeypatch.setattr(
        CountryService,
        "get_country",
        fake_get,
    )

    response = client.get(
        "/api/v1/countries/CI",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json()["iso2"] == "CI"
    assert response.json()["iso3"] == "CIV"
    assert captured["iso2"] == "CI"


def test_continent_code_is_normalized_to_uppercase(
    client: TestClient,
    country_dependencies,
    monkeypatch,
) -> None:
    captured = {}

    async def fake_list(
        self,
        *,
        continent_code=None,
        search=None,
    ):
        captured["continent_code"] = continent_code
        return [country_object()]

    monkeypatch.setattr(
        CountryService,
        "list_countries",
        fake_list,
    )

    response = client.get(
        "/api/v1/countries?continent_code=af",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert captured["continent_code"] == "AF"


def test_invalid_continent_code_returns_422(
    client: TestClient,
    country_dependencies,
) -> None:
    response = client.get(
        "/api/v1/countries?continent_code=AFRICA",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 422
