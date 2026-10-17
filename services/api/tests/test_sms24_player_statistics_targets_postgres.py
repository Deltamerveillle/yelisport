"""Automatic Player Statistics target discovery in disposable PostgreSQL."""

import uuid

import pytest
from sqlalchemy import select

from app.models.sport import Sport
from app.models.sports_live import (
    SportsCanonicalCompetitor,
    SportsCompetitor,
    SportsDataSource,
    SportsDataSourceCapability,
)
from app.sms24.player_statistics_targets import PlayerStatisticsTargetDiscovery
from tests import test_sms24_player_statistics_postgres as foundation
from tests.test_sms24_transfers_postgres import add

previous_connection = foundation.previous_connection
connection = foundation.connection
session = foundation.session


async def setup_source(session, *, slug="sportmonks", capability=True):
    sport = await add(session, Sport, slug=f"football-{uuid.uuid4()}", name="Football")
    source = await add(
        session,
        SportsDataSource,
        slug=slug,
        name=slug,
    )
    if capability:
        await add(
            session,
            SportsDataSourceCapability,
            source_id=source.id,
            capability="statistics",
            is_active=True,
        )
    return sport, source


async def add_athlete(
    session,
    *,
    sport,
    source,
    external_id,
    identity_scope="provider_scoped",
    canonical_type="athlete",
    competitor_type="athlete",
):
    canonical = await add(
        session,
        SportsCanonicalCompetitor,
        sport_id=sport.id,
        identity_scope=identity_scope,
        canonical_key=f"{source.slug}:{external_id}:{uuid.uuid4()}",
        competitor_type=canonical_type,
        name=f"Player {external_id}",
        normalized_name=f"player {external_id}",
    )
    competitor = await add(
        session,
        SportsCompetitor,
        sport_id=sport.id,
        source_id=source.id,
        canonical_competitor_id=canonical.id,
        external_id=external_id,
        competitor_type=competitor_type,
        name=f"Player {external_id}",
    )
    return competitor, canonical


async def test_discovers_only_provider_scoped_athletes_with_active_statistics(session):
    sport, source = await setup_source(session)

    await add_athlete(session, sport=sport, source=source, external_id="10")
    await add_athlete(session, sport=sport, source=source, external_id="20")

    result = await PlayerStatisticsTargetDiscovery(
        session=session,
        provider_slug="sportmonks",
    ).discover()

    assert [(t.provider_slug, t.athlete_external_id, t.sport_id) for t in result.targets] == [
        ("sportmonks", "10", sport.id),
        ("sportmonks", "20", sport.id),
    ]
    assert result.reason is None
    assert result.next_cursor is None
    assert result.has_more is False


async def test_excludes_non_provider_scoped_non_athlete_and_inactive_sport(session):
    sport, source = await setup_source(session)

    await add_athlete(session, sport=sport, source=source, external_id="10")
    await add_athlete(
        session,
        sport=sport,
        source=source,
        external_id="20",
        identity_scope="verified_context",
    )
    await add_athlete(
        session,
        sport=sport,
        source=source,
        external_id="30",
        canonical_type="team",
        competitor_type="team",
    )

    inactive = await add(
        session,
        Sport,
        slug=f"inactive-{uuid.uuid4()}",
        name="Inactive",
        is_active=False,
    )
    await add_athlete(
        session,
        sport=inactive,
        source=source,
        external_id="40",
    )

    result = await PlayerStatisticsTargetDiscovery(
        session=session,
        provider_slug="sportmonks",
    ).discover()

    assert [t.athlete_external_id for t in result.targets] == ["10"]


async def test_requires_active_statistics_capability(session):
    _, _ = await setup_source(session, capability=False)

    result = await PlayerStatisticsTargetDiscovery(
        session=session,
        provider_slug="sportmonks",
    ).discover()

    assert result.targets == ()
    assert result.reason == "statistics_capability_not_active"


async def test_pagination_is_deterministic_and_bounded(session):
    sport, source = await setup_source(session)

    for external_id in ("30", "10", "20"):
        await add_athlete(
            session,
            sport=sport,
            source=source,
            external_id=external_id,
        )

    discovery = PlayerStatisticsTargetDiscovery(
        session=session,
        provider_slug="sportmonks",
        max_players=2,
    )

    first = await discovery.discover()

    assert [t.athlete_external_id for t in first.targets] == ["10", "20"]
    assert first.next_cursor == "20"
    assert first.has_more is True

    second = await discovery.discover(after_player_external_id=first.next_cursor)

    assert [t.athlete_external_id for t in second.targets] == ["30"]
    assert second.next_cursor is None
    assert second.has_more is False


async def test_provider_sources_are_isolated(session):
    sport, sportmonks = await setup_source(session, slug="sportmonks")
    _, other = await setup_source(session, slug="other")

    await add_athlete(
        session,
        sport=sport,
        source=sportmonks,
        external_id="10",
    )
    await add_athlete(
        session,
        sport=sport,
        source=other,
        external_id="10",
    )

    result = await PlayerStatisticsTargetDiscovery(
        session=session,
        provider_slug="sportmonks",
    ).discover()

    assert len(result.targets) == 1
    assert result.targets[0].provider_slug == "sportmonks"
    assert result.targets[0].athlete_external_id == "10"


@pytest.mark.parametrize("cursor", ["", " 10", "10 ", "\x00", "x" * 161])
async def test_invalid_cursor_rejected(session, cursor):
    with pytest.raises(ValueError):
        await PlayerStatisticsTargetDiscovery(
            session=session,
            provider_slug="sportmonks",
        ).discover(after_player_external_id=cursor)


async def test_inactive_source_is_not_eligible(session):
    sport, source = await setup_source(session)
    source.is_active = False
    await session.flush()

    await add_athlete(
        session,
        sport=sport,
        source=source,
        external_id="10",
    )

    result = await PlayerStatisticsTargetDiscovery(
        session=session,
        provider_slug="sportmonks",
    ).discover()

    assert result.targets == ()
    assert result.reason == "statistics_capability_not_active"


async def test_excludes_athlete_without_canonical_identity(session):
    sport, source = await setup_source(session)

    await add(
        session,
        SportsCompetitor,
        sport_id=sport.id,
        source_id=source.id,
        canonical_competitor_id=None,
        external_id="10",
        competitor_type="athlete",
        name="Player 10",
    )

    result = await PlayerStatisticsTargetDiscovery(
        session=session,
        provider_slug="sportmonks",
    ).discover()

    assert result.targets == ()


async def test_excludes_athlete_with_canonical_from_different_sport(session):
    sport, source = await setup_source(session)
    other_sport = await add(
        session,
        Sport,
        slug=f"other-{uuid.uuid4()}",
        name="Other Sport",
    )

    canonical = await add(
        session,
        SportsCanonicalCompetitor,
        sport_id=other_sport.id,
        identity_scope="provider_scoped",
        canonical_key=f"{source.slug}:10:{uuid.uuid4()}",
        competitor_type="athlete",
        name="Player 10",
        normalized_name="player 10",
    )

    await add(
        session,
        SportsCompetitor,
        sport_id=sport.id,
        source_id=source.id,
        canonical_competitor_id=canonical.id,
        external_id="10",
        competitor_type="athlete",
        name="Player 10",
    )

    result = await PlayerStatisticsTargetDiscovery(
        session=session,
        provider_slug="sportmonks",
    ).discover()

    assert result.targets == ()


async def test_excludes_athlete_with_non_athlete_canonical_identity(session):
    sport, source = await setup_source(session)

    canonical = await add(
        session,
        SportsCanonicalCompetitor,
        sport_id=sport.id,
        identity_scope="provider_scoped",
        canonical_key=f"{source.slug}:10:{uuid.uuid4()}",
        competitor_type="team",
        name="Player 10",
        normalized_name="player 10",
    )

    await add(
        session,
        SportsCompetitor,
        sport_id=sport.id,
        source_id=source.id,
        canonical_competitor_id=canonical.id,
        external_id="10",
        competitor_type="athlete",
        name="Player 10",
    )

    result = await PlayerStatisticsTargetDiscovery(
        session=session,
        provider_slug="sportmonks",
    ).discover()

    assert result.targets == ()


async def test_inactive_statistics_capability_is_not_eligible(session):
    _, source = await setup_source(session)

    capability = await session.scalar(
        select(SportsDataSourceCapability).where(
            SportsDataSourceCapability.source_id == source.id,
            SportsDataSourceCapability.capability == "statistics",
        )
    )
    assert capability is not None

    capability.is_active = False
    await session.flush()

    result = await PlayerStatisticsTargetDiscovery(
        session=session,
        provider_slug="sportmonks",
    ).discover()

    assert result.targets == ()
    assert result.reason == "statistics_capability_not_active"
