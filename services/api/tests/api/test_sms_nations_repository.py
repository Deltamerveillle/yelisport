"""Tests for SMS Nations discovery repository."""

import uuid

import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.sms_nations_repository import SMSNationsRepository


ATHLETE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SPORT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
CI_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
FR_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
VIDEO_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")


class FakeMappings:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return FakeMappings(self.rows)


class FakeSession:
    def __init__(self, *, total=1, rows=None):
        self.total = total
        self.rows = rows or []
        self.scalar_statements = []
        self.execute_statements = []

    async def scalar(self, statement):
        self.scalar_statements.append(statement)
        return self.total

    async def execute(self, statement):
        self.execute_statements.append(statement)
        return FakeResult(self.rows)


def sql_text(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


@pytest.mark.asyncio
async def test_search_returns_sms_nations_athlete_card():
    session = FakeSession(
        total=1,
        rows=[
            {
                "athlete_id": ATHLETE_ID,
                "first_name": "Awa",
                "last_name": "Kouassi",
                "city": "Paris",
                "avatar_url": "https://example.com/awa.jpg",
                "sport_id": SPORT_ID,
                "sport_slug": "football",
                "sport_name": "Football",
                "residence_country_id": FR_ID,
                "residence_country_iso2": "FR",
                "residence_country_name": "France",
                "discipline": "Football",
                "category": "Senior",
                "position": "Attaquant",
                "club_name": "Paris Talent FC",
                "league_name": "Ligue 1",
                "team_name": None,
                "available_for_opportunities": True,
                "eligibility_country_id": CI_ID,
                "eligibility_status": "verified",
                "eligibility_is_primary": True,
                "discover_video_id": VIDEO_ID,
                "discover_video_url": "https://example.com/video.mp4",
                "discover_thumbnail_url": "https://example.com/thumb.jpg",
                "discover_caption": "Attaquant ivoirien en France",
                "discover_duration_seconds": 20,
            }
        ],
    )

    repository = SMSNationsRepository(session)

    result = await repository.search_athletes(
        eligibility_country_id=CI_ID,
        residence_country_id=FR_ID,
        sport_id=SPORT_ID,
        eligibility_status="verified",
    )

    assert result.total == 1
    assert result.limit == 24
    assert result.offset == 0
    assert len(result.items) == 1

    athlete = result.items[0]

    assert athlete.athlete_id == ATHLETE_ID
    assert athlete.first_name == "Awa"
    assert athlete.avatar_url == "https://example.com/awa.jpg"
    assert athlete.residence_country_iso2 == "FR"
    assert athlete.eligibility_country_id == CI_ID
    assert athlete.eligibility_status == "verified"
    assert athlete.discover_video_id == VIDEO_ID
    assert athlete.discover_duration_seconds == 20


@pytest.mark.asyncio
async def test_diaspora_query_filters_eligibility_and_residence():
    session = FakeSession(total=0)
    repository = SMSNationsRepository(session)

    await repository.search_athletes(
        eligibility_country_id=CI_ID,
        residence_country_id=FR_ID,
        sport_id=SPORT_ID,
    )

    sql = sql_text(session.execute_statements[0])

    assert str(CI_ID) in sql
    assert str(FR_ID) in sql
    assert str(SPORT_ID) in sql
    assert "athlete_country_eligibilities" in sql
    assert "residence_country_id" in sql


@pytest.mark.asyncio
async def test_only_approved_public_active_discover_video_is_selected():
    session = FakeSession(total=0)
    repository = SMSNationsRepository(session)

    await repository.search_athletes()

    sql = sql_text(session.execute_statements[0])

    assert "publication_status = 'published'" in sql
    assert "moderation_status = 'approved'" in sql
    assert "visibility = 'public'" in sql
    assert "is_active IS true" in sql
    assert "row_number()" in sql.lower()


@pytest.mark.asyncio
async def test_passport_filters_are_applied():
    session = FakeSession(total=0)
    repository = SMSNationsRepository(session)

    await repository.search_athletes(
        discipline="football",
        category="senior",
        position="attaquant",
        club="academy",
        city="paris",
        available_for_opportunities=True,
    )

    sql = sql_text(session.execute_statements[0]).lower()

    assert "discipline" in sql
    assert "category" in sql
    assert "position" in sql
    assert "club_name" in sql
    assert "team_name" in sql
    assert "city" in sql
    assert "available_for_opportunities = true" in sql


@pytest.mark.asyncio
async def test_pagination_is_clamped_safely():
    session = FakeSession(total=250)
    repository = SMSNationsRepository(session)

    result = await repository.search_athletes(
        limit=1000,
        offset=-50,
    )

    assert result.limit == 100
    assert result.offset == 0
    assert result.total == 250

    sql = sql_text(session.execute_statements[0])

    assert "LIMIT 100" in sql
    assert "OFFSET 0" in sql


@pytest.mark.asyncio
async def test_result_contains_no_personal_contact_fields():
    session = FakeSession(
        total=1,
        rows=[
            {
                "athlete_id": ATHLETE_ID,
                "first_name": "Awa",
                "last_name": "Kouassi",
                "city": "Paris",
                "avatar_url": "https://example.com/awa.jpg",
                "sport_id": SPORT_ID,
                "sport_slug": "football",
                "sport_name": "Football",
                "residence_country_id": FR_ID,
                "residence_country_iso2": "FR",
                "residence_country_name": "France",
                "discipline": "Football",
                "category": None,
                "position": "Attaquant",
                "club_name": None,
                "league_name": "Ligue 1",
                "team_name": None,
                "available_for_opportunities": True,
                "eligibility_country_id": CI_ID,
                "eligibility_status": "declared",
                "eligibility_is_primary": True,
                "discover_video_id": None,
                "discover_video_url": None,
                "discover_thumbnail_url": None,
                "discover_caption": None,
                "discover_duration_seconds": None,
            }
        ],
    )

    repository = SMSNationsRepository(session)
    result = await repository.search_athletes()

    athlete = result.items[0]

    assert not hasattr(athlete, "email")
    assert not hasattr(athlete, "phone")
    assert not hasattr(athlete, "whatsapp")
    assert not hasattr(athlete, "user_id")


@pytest.mark.asyncio
async def test_age_filters_use_profile_birth_date():
    session = FakeSession(total=0)
    repository = SMSNationsRepository(session)

    await repository.search_athletes(
        min_age=16,
        max_age=18,
    )

    sql = sql_text(session.execute_statements[0]).lower()

    assert "birth_date" in sql
    assert "profiles" in sql
