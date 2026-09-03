"""Repository for SMS Nations athlete discovery."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.athlete import Athlete
from app.models.athlete_country_eligibility import AthleteCountryEligibility
from app.models.athlete_passport import AthletePassport
from app.models.country import Country
from app.models.discover_video import DiscoverVideo
from app.models.sport import Sport
from app.models.user import Profile


@dataclass(slots=True)
class SMSNationAthleteRow:
    """One athlete card returned by SMS Nations discovery."""

    athlete_id: uuid.UUID
    first_name: str
    last_name: str
    city: str | None
    avatar_url: str | None

    sport_id: uuid.UUID
    sport_slug: str
    sport_name: str

    residence_country_id: uuid.UUID | None
    residence_country_iso2: str | None
    residence_country_name: str | None

    discipline: str | None
    category: str | None
    position: str | None
    club_name: str | None
    team_name: str | None
    available_for_opportunities: bool | None

    eligibility_country_id: uuid.UUID | None
    eligibility_status: str | None
    eligibility_is_primary: bool | None

    discover_video_id: uuid.UUID | None
    discover_video_url: str | None
    discover_thumbnail_url: str | None
    discover_caption: str | None
    discover_duration_seconds: int | None


@dataclass(slots=True)
class SMSNationsSearchResult:
    """Paginated SMS Nations discovery result."""

    items: list[SMSNationAthleteRow]
    total: int
    limit: int
    offset: int


class SMSNationsRepository:
    """Optimized search for Country -> Sport -> Athletes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search_athletes(
        self,
        *,
        eligibility_country_id: uuid.UUID | None = None,
        sport_id: uuid.UUID | None = None,
        residence_country_id: uuid.UUID | None = None,
        discipline: str | None = None,
        category: str | None = None,
        position: str | None = None,
        club: str | None = None,
        city: str | None = None,
        available_for_opportunities: bool | None = None,
        eligibility_status: str | None = None,
        search: str | None = None,
        limit: int = 24,
        offset: int = 0,
    ) -> SMSNationsSearchResult:
        """
        Search SMS Nations athlete cards.

        The query:
        - supports African-country eligibility and diaspora residence;
        - loads passport and sport data in one query;
        - returns at most one approved public Discover video per athlete;
        - never exposes athlete personal contact information;
        - avoids N+1 queries.
        """

        limit = max(1, min(limit, 100))
        offset = max(0, offset)

        residence_country = aliased(Country)

        latest_video = (
            select(
                DiscoverVideo.id.label("video_id"),
                DiscoverVideo.athlete_id.label("athlete_id"),
                DiscoverVideo.video_url.label("video_url"),
                DiscoverVideo.thumbnail_url.label("thumbnail_url"),
                DiscoverVideo.caption.label("caption"),
                DiscoverVideo.duration_seconds.label("duration_seconds"),
                func.row_number()
                .over(
                    partition_by=DiscoverVideo.athlete_id,
                    order_by=DiscoverVideo.created_at.desc(),
                )
                .label("rn"),
            )
            .where(
                DiscoverVideo.publication_status == "published",
                DiscoverVideo.moderation_status == "approved",
                DiscoverVideo.visibility == "public",
                DiscoverVideo.is_active.is_(True),
            )
            .subquery("latest_public_discover_video")
        )

        conditions: list[Any] = [
            Sport.is_active.is_(True),
        ]

        if sport_id is not None:
            conditions.append(Athlete.sport_id == sport_id)

        if residence_country_id is not None:
            conditions.append(
                Athlete.residence_country_id == residence_country_id
            )

        if discipline:
            conditions.append(
                AthletePassport.discipline.ilike(
                    f"%{discipline.strip()}%"
                )
            )

        if category:
            conditions.append(
                AthletePassport.category.ilike(
                    f"%{category.strip()}%"
                )
            )

        if position:
            conditions.append(
                AthletePassport.position.ilike(
                    f"%{position.strip()}%"
                )
            )

        if club:
            club_term = f"%{club.strip()}%"
            conditions.append(
                or_(
                    AthletePassport.club_name.ilike(club_term),
                    AthletePassport.team_name.ilike(club_term),
                )
            )

        if city:
            conditions.append(
                Athlete.city.ilike(f"%{city.strip()}%")
            )

        if available_for_opportunities is not None:
            conditions.append(
                AthletePassport.available_for_opportunities
                == available_for_opportunities
            )

        if search:
            needle = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Athlete.first_name.ilike(needle),
                    Athlete.last_name.ilike(needle),
                    Athlete.city.ilike(needle),
                    AthletePassport.discipline.ilike(needle),
                    AthletePassport.category.ilike(needle),
                    AthletePassport.position.ilike(needle),
                    AthletePassport.club_name.ilike(needle),
                    AthletePassport.team_name.ilike(needle),
                )
            )

        eligibility_filters = [
            AthleteCountryEligibility.athlete_id == Athlete.id,
        ]

        if eligibility_country_id is not None:
            eligibility_filters.append(
                AthleteCountryEligibility.country_id
                == eligibility_country_id
            )

        if eligibility_status is not None:
            eligibility_filters.append(
                AthleteCountryEligibility.status
                == eligibility_status
            )

            if eligibility_country_id is None:
                eligibility_filters.append(
                    AthleteCountryEligibility.is_primary.is_(True)
                )

        if (
            eligibility_country_id is not None
            or eligibility_status is not None
        ):
            conditions.append(
                exists(
                    select(1).where(*eligibility_filters)
                )
            )

        selected_eligibility = aliased(AthleteCountryEligibility)

        eligibility_join_conditions = [
            selected_eligibility.athlete_id == Athlete.id,
        ]

        if eligibility_country_id is not None:
            eligibility_join_conditions.append(
                selected_eligibility.country_id
                == eligibility_country_id
            )
        else:
            eligibility_join_conditions.append(
                selected_eligibility.is_primary.is_(True)
            )

        if eligibility_status is not None:
            eligibility_join_conditions.append(
                selected_eligibility.status
                == eligibility_status
            )

        stmt = (
            select(
                Athlete.id.label("athlete_id"),
                Athlete.first_name,
                Athlete.last_name,
                Athlete.city,
                Profile.avatar_url.label("avatar_url"),
                Sport.id.label("sport_id"),
                Sport.slug.label("sport_slug"),
                Sport.name.label("sport_name"),
                residence_country.id.label(
                    "residence_country_id"
                ),
                residence_country.iso2.label(
                    "residence_country_iso2"
                ),
                residence_country.name.label(
                    "residence_country_name"
                ),
                AthletePassport.discipline,
                AthletePassport.category,
                AthletePassport.position,
                AthletePassport.club_name,
                AthletePassport.team_name,
                AthletePassport.available_for_opportunities,
                selected_eligibility.country_id.label(
                    "eligibility_country_id"
                ),
                selected_eligibility.status.label(
                    "eligibility_status"
                ),
                selected_eligibility.is_primary.label(
                    "eligibility_is_primary"
                ),
                latest_video.c.video_id.label(
                    "discover_video_id"
                ),
                latest_video.c.video_url.label(
                    "discover_video_url"
                ),
                latest_video.c.thumbnail_url.label(
                    "discover_thumbnail_url"
                ),
                latest_video.c.caption.label(
                    "discover_caption"
                ),
                latest_video.c.duration_seconds.label(
                    "discover_duration_seconds"
                ),
            )
            .join(
                Sport,
                Sport.id == Athlete.sport_id,
            )
            .outerjoin(
                Profile,
                Profile.user_id == Athlete.user_id,
            )
            .outerjoin(
                AthletePassport,
                AthletePassport.athlete_id == Athlete.id,
            )
            .outerjoin(
                residence_country,
                residence_country.id
                == Athlete.residence_country_id,
            )
            .outerjoin(
                selected_eligibility,
                and_(*eligibility_join_conditions),
            )
            .outerjoin(
                latest_video,
                and_(
                    latest_video.c.athlete_id == Athlete.id,
                    latest_video.c.rn == 1,
                ),
            )
            .where(*conditions)
            .order_by(
                Athlete.updated_at.desc(),
                Athlete.id,
            )
            .offset(offset)
            .limit(limit)
        )

        count_stmt = (
            select(func.count(Athlete.id))
            .join(
                Sport,
                Sport.id == Athlete.sport_id,
            )
            .outerjoin(
                AthletePassport,
                AthletePassport.athlete_id == Athlete.id,
            )
            .where(*conditions)
        )

        total = int(
            (await self.session.scalar(count_stmt)) or 0
        )

        result = await self.session.execute(stmt)

        items = [
            SMSNationAthleteRow(**dict(row))
            for row in result.mappings().all()
        ]

        return SMSNationsSearchResult(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )
