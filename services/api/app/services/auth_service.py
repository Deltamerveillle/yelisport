"""Supabase Auth gateway isolated from HTTP routing."""

from typing import Any

from supabase import Client, create_client

from app.core.config import Settings, get_settings
from app.core.exceptions import ApplicationError
from app.schemas.auth import AuthSession, AuthUser, SignUpResponse


class AuthService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: Client | None = None,
        admin_client: Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or create_client(
            self.settings.supabase_url, self.settings.supabase_anon_key
        )
        self.admin_client = admin_client or create_client(
            self.settings.supabase_url, self.settings.supabase_service_role_key
        )

    def sign_up(self, email: str, password: str, display_name: str | None) -> SignUpResponse:
        try:
            response = self.client.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {"data": {"display_name": display_name}},
                }
            )
        except Exception as exc:
            raise ApplicationError(
                "Impossible de créer le compte", code="auth_signup_failed", status_code=400
            ) from exc
        user = self._user(response.user)
        session = self._session(response.session) if response.session else None
        return SignUpResponse(user=user, session=session, confirmation_required=session is None)

    def sign_in(self, email: str, password: str) -> AuthSession:
        try:
            response = self.client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
        except Exception as exc:
            raise ApplicationError(
                "Identifiants invalides", code="invalid_credentials", status_code=401
            ) from exc
        if response.session is None:
            raise ApplicationError(
                "Identifiants invalides", code="invalid_credentials", status_code=401
            )
        return self._session(response.session)

    def refresh(self, refresh_token: str) -> AuthSession:
        try:
            response = self.client.auth.refresh_session(refresh_token)
        except Exception as exc:
            raise ApplicationError(
                "Session invalide", code="invalid_refresh_token", status_code=401
            ) from exc
        if response.session is None:
            raise ApplicationError(
                "Session invalide", code="invalid_refresh_token", status_code=401
            )
        return self._session(response.session)

    def user_from_token(self, access_token: str) -> AuthUser:
        try:
            response = self.client.auth.get_user(access_token)
        except Exception as exc:
            raise ApplicationError(
                "Jeton invalide ou expiré", code="invalid_access_token", status_code=401
            ) from exc
        return self._user(response.user)

    def sign_out(self, access_token: str) -> None:
        try:
            self.admin_client.auth.admin.sign_out(access_token)
        except Exception as exc:
            raise ApplicationError(
                "Déconnexion impossible", code="signout_failed", status_code=400
            ) from exc

    @staticmethod
    def _user(user: Any) -> AuthUser:
        if user is None:
            raise ApplicationError(
                "Réponse d'authentification invalide",
                code="invalid_auth_response",
                status_code=502,
            )
        return AuthUser(id=str(user.id), email=user.email)

    @classmethod
    def _session(cls, session: Any) -> AuthSession:
        return AuthSession(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=session.expires_in,
            user=cls._user(session.user),
        )
