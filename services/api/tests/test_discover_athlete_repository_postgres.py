"""SMS Discover athlete search in disposable PostgreSQL."""

import uuid

from app.models.athlete import Athlete
from app.models.athlete_passport import AthletePassport
from app.models.country import Country
from app.models.sport import Sport
from app.models.user import User
from app.repositories.discover_athlete_repository import DiscoverAthleteRepository
from tests import test_sms24_player_statistics_postgres as foundation
from tests.test_sms24_transfers_postgres import add

previous_connection = foundation.previous_connection
connection = foundation.connection
session = foundation.session


async def create_discoverable_athlete(
    session,
    *,
    sport,
    country,
    suffix,
    available=True,
    discipline="Football",
    category="Senior",
    position="Forward",
    club_name="SMS FC",
    league_name="SMS League",
    team_name="SMS Team",
):
    user = await add(
        session,
        User,
        id=uuid.uuid4(),
        email=f"discover-{suffix}-{uuid.uuid4()}@example.com",
    )

    athlete = await add(
        session,
        Athlete,
        user_id=user.id,
        sport_id=sport.id,
        first_name=f"Player {suffix}",
        last_name="Discover",
        nationality="Ivorian",
        country="Côte d'Ivoire",
        residence_country_id=country.id,
        city="Abidjan",
    )

    passport = await add(
        session,
        AthletePassport,
        athlete_id=athlete.id,
        discipline=discipline,
        category=category,
        position=position,
        club_name=club_name,
        league_name=league_name,
        team_name=team_name,
        available_for_opportunities=available,
        sporting_summary=f"Discover athlete {suffix}",
    )

    return athlete, passport


async def test_search_requires_explicit_opportunity_opt_in(session):
    sport = await add(
        session,
        Sport,
        slug=f"football-{uuid.uuid4()}",
        name="Football",
    )
    country = await add(
        session,
        Country,
        iso2=uuid.uuid4().hex[:2].upper(),
        iso3=uuid.uuid4().hex[:3].upper(),
        name=f"Discover Country {uuid.uuid4()}",
    )

    visible, _ = await create_discoverable_athlete(
        session,
        sport=sport,
        country=country,
        suffix="visible",
        available=True,
    )
    await create_discoverable_athlete(
        session,
        sport=sport,
        country=country,
        suffix="hidden",
        available=False,
    )

    results = await DiscoverAthleteRepository(session).search(
        sport_id=sport.id,
    )

    assert [item.athlete.id for item in results] == [visible.id]


async def test_search_filters_passport_fields_case_insensitively(session):
    sport = await add(
        session,
        Sport,
        slug=f"football-{uuid.uuid4()}",
        name="Football",
    )
    country = await add(
        session,
        Country,
        iso2=uuid.uuid4().hex[:2].upper(),
        iso3=uuid.uuid4().hex[:3].upper(),
        name=f"Discover Country {uuid.uuid4()}",
    )

    expected, _ = await create_discoverable_athlete(
        session,
        sport=sport,
        country=country,
        suffix="forward",
        discipline="Football",
        category="Senior",
        position="Forward",
        club_name="Abidjan Stars",
        league_name="Premier League",
        team_name="Stars A",
    )
    await create_discoverable_athlete(
        session,
        sport=sport,
        country=country,
        suffix="keeper",
        position="Goalkeeper",
        club_name="Other Club",
    )

    results = await DiscoverAthleteRepository(session).search(
        discipline="football",
        category="senior",
        position="forward",
        club_name="abidjan stars",
        league_name="premier league",
        team_name="stars a",
    )

    assert [item.athlete.id for item in results] == [expected.id]


async def test_search_combines_sport_and_residence_country(session):
    football = await add(
        session,
        Sport,
        slug=f"football-{uuid.uuid4()}",
        name="Football",
    )
    basketball = await add(
        session,
        Sport,
        slug=f"basketball-{uuid.uuid4()}",
        name="Basketball",
    )
    country_a = await add(
        session,
        Country,
        iso2=uuid.uuid4().hex[:2].upper(),
        iso3=uuid.uuid4().hex[:3].upper(),
        name=f"Country A {uuid.uuid4()}",
    )
    country_b = await add(
        session,
        Country,
        iso2=uuid.uuid4().hex[:2].upper(),
        iso3=uuid.uuid4().hex[:3].upper(),
        name=f"Country B {uuid.uuid4()}",
    )

    expected, _ = await create_discoverable_athlete(
        session,
        sport=football,
        country=country_a,
        suffix="expected",
    )
    await create_discoverable_athlete(
        session,
        sport=football,
        country=country_b,
        suffix="wrong-country",
    )
    await create_discoverable_athlete(
        session,
        sport=basketball,
        country=country_a,
        suffix="wrong-sport",
    )

    results = await DiscoverAthleteRepository(session).search(
        sport_id=football.id,
        residence_country_id=country_a.id,
    )

    assert [item.athlete.id for item in results] == [expected.id]


async def test_search_pagination_is_deterministic(session):
    sport = await add(
        session,
        Sport,
        slug=f"football-{uuid.uuid4()}",
        name="Football",
    )
    country = await add(
        session,
        Country,
        iso2=uuid.uuid4().hex[:2].upper(),
        iso3=uuid.uuid4().hex[:3].upper(),
        name=f"Pagination Country {uuid.uuid4()}",
    )

    athletes = []
    for suffix in ("one", "two", "three"):
        athlete, _ = await create_discoverable_athlete(
            session,
            sport=sport,
            country=country,
            suffix=suffix,
        )
        athletes.append(athlete)

    repository = DiscoverAthleteRepository(session)

    all_results = await repository.search(
        sport_id=sport.id,
        residence_country_id=country.id,
        limit=10,
        offset=0,
    )
    first_page = await repository.search(
        sport_id=sport.id,
        residence_country_id=country.id,
        limit=2,
        offset=0,
    )
    second_page = await repository.search(
        sport_id=sport.id,
        residence_country_id=country.id,
        limit=2,
        offset=2,
    )

    all_ids = [item.athlete.id for item in all_results]

    assert len(all_ids) == 3
    assert set(all_ids) == {athlete.id for athlete in athletes}
    assert [item.athlete.id for item in first_page] == all_ids[:2]
    assert [item.athlete.id for item in second_page] == all_ids[2:]


async def test_get_discoverable_by_athlete_id_requires_opportunity_opt_in(session):
    sport = await add(
        session,
        Sport,
        name=f"Football {uuid.uuid4()}",
        slug=f"football-{uuid.uuid4()}",
        is_active=True,
    )
    country = await add(
        session,
        Country,
        iso2="CI",
        iso3=f"C{uuid.uuid4().hex[:2]}".upper(),
        name=f"Côte d'Ivoire {uuid.uuid4()}",
        continent_code="AF",
        is_active=True,
    )

    visible_athlete, visible_passport = await create_discoverable_athlete(
        session,
        sport=sport,
        country=country,
        suffix="detail-visible",
        available=True,
    )
    hidden_athlete, _ = await create_discoverable_athlete(
        session,
        sport=sport,
        country=country,
        suffix="detail-hidden",
        available=False,
    )

    repository = DiscoverAthleteRepository(session)

    visible = await repository.get_discoverable_by_athlete_id(
        visible_athlete.id
    )
    hidden = await repository.get_discoverable_by_athlete_id(
        hidden_athlete.id
    )
    missing = await repository.get_discoverable_by_athlete_id(uuid.uuid4())

    assert visible is not None
    assert visible.athlete.id == visible_athlete.id
    assert visible.passport.id == visible_passport.id
    assert hidden is None
    assert missing is None
