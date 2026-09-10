"""Database models exported for Alembic discovery."""

from app.models.user import Profile, User
from app.models.user_role import UserRole
from app.models.user_preferences import (
    FavoriteEvent,
    FavoriteSport,
    UserSettings,
)

from app.models.sport import Sport
from app.models.country import Country

from app.models.athlete import Athlete
from app.models.athlete_country_eligibility import AthleteCountryEligibility
from app.models.athlete_passport import AthletePassport
from app.models.athlete_performance import AthletePerformance

from app.models.discover_video import DiscoverVideo

from app.models.event import (
    Event,
    EventRegistration,
    RegistrationStatus,
)

from app.models.subscription import Subscription
from app.models.payment_transaction import PaymentTransaction
from app.models.yeleni_pay_event import YeleniPayEvent

from app.models.talent_application import TalentApplication
from app.models.talent_evaluation import TalentEvaluation
from app.models.talent_submission_item import TalentSubmissionItem

from app.models.sms_connect_interest import SMSConnectInterest
from app.models.sms_connect_interest_event import SMSConnectInterestEvent

from app.models.notification import Notification

from app.models.moderation_report import (
    ModerationReport,
    ModerationReportEvent,
)

from app.models.sports_live import (
    SportsCanonicalFixture,
    SportsCompetition,
    SportsCompetitor,
    SportsDataSource,
    SportsFixture,
    SportsFixtureParticipant,
)


__all__ = [
    "User",
    "Profile",
    "UserRole",
    "UserSettings",
    "FavoriteSport",
    "FavoriteEvent",
    "Sport",
    "Country",
    "Athlete",
    "AthleteCountryEligibility",
    "AthletePassport",
    "AthletePerformance",
    "DiscoverVideo",
    "Event",
    "EventRegistration",
    "RegistrationStatus",
    "Subscription",
    "PaymentTransaction",
    "YeleniPayEvent",
    "TalentApplication",
    "TalentEvaluation",
    "TalentSubmissionItem",
    "SMSConnectInterest",
    "SMSConnectInterestEvent",
    "Notification",
    "ModerationReport",
    "ModerationReportEvent",
    "SportsDataSource",
    "SportsCanonicalFixture",
    "SportsCompetition",
    "SportsCompetitor",
    "SportsFixture",
    "SportsFixtureParticipant",
]
