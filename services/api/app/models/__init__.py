"""Database models exported for Alembic discovery."""

from app.models.event import Event, EventRegistration, RegistrationStatus
from app.models.sport import Sport
from app.models.user import Profile, User
from app.models.user_role import UserRole
from app.models.user_preferences import FavoriteEvent, FavoriteSport, UserSettings

__all__ = [
    "Event",
    "EventRegistration",
    "FavoriteEvent",
    "FavoriteSport",
    "Profile",
    "RegistrationStatus",
    "Sport",
    "User",
    "UserRole",
    "UserSettings",
]
