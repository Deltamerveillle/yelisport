from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_auth_service
from app.schemas.auth import AuthSession, AuthUser, SignUpResponse


class FakeAuthService:
    user = AuthUser(id="28bbf25e-8d42-4a0a-8bc8-0f41be0fc114", email="test@yelisport.ci")

    def sign_up(self, email: str, password: str, display_name: str | None) -> SignUpResponse:
        return SignUpResponse(user=self.user, confirmation_required=True)

    def sign_in(self, email: str, password: str) -> AuthSession:
        return self.session()

    def refresh(self, refresh_token: str) -> AuthSession:
        return self.session()

    def user_from_token(self, access_token: str) -> AuthUser:
        return self.user

    def sign_out(self, access_token: str) -> None:
        return None

    def session(self) -> AuthSession:
        return AuthSession(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=3600,
            user=self.user,
        )


def override_auth(client: TestClient) -> None:
    client.app.dependency_overrides[get_auth_service] = FakeAuthService


def test_sign_up_requires_valid_password(client: TestClient) -> None:
    override_auth(client)
    response = client.post(
        "/api/v1/auth/sign-up", json={"email": "test@yelisport.ci", "password": "short"}
    )
    assert response.status_code == 422


def test_sign_up_returns_confirmation_state(client: TestClient) -> None:
    override_auth(client)
    response = client.post(
        "/api/v1/auth/sign-up",
        json={"email": "test@yelisport.ci", "password": "safe-password"},
    )
    assert response.status_code == 201
    assert response.json()["confirmation_required"] is True


def test_sign_in_returns_session(client: TestClient) -> None:
    override_auth(client)
    response = client.post(
        "/api/v1/auth/sign-in",
        json={"email": "test@yelisport.ci", "password": "safe-password"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"] == "access-token"


def test_me_requires_bearer_token(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 403


def test_me_returns_authenticated_user(client: TestClient) -> None:
    override_auth(client)
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer access-token"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "test@yelisport.ci"
