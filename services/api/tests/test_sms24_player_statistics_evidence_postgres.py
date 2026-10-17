import uuid

import pytest

from app.sms24.player_statistics_evidence import AthleteStatisticsEvidenceReader
from tests import test_sms24_player_statistics_postgres as statistics
from tests import test_sms24_transfers_postgres as transfers

previous_connection = statistics.previous_connection
connection = statistics.connection
session = statistics.session
add = statistics.add


async def test_unlinked_human_athlete_receives_no_provider_evidence(session):
    sport = await add(
        session,
        transfers.Sport,
        slug=f"football-{uuid.uuid4().hex}",
        name="Football",
    )
    athlete = await transfers.human(session, sport)

    result = await AthleteStatisticsEvidenceReader(session=session).read(
        athlete_id=athlete.id,
    )

    assert result.athlete_id == athlete.id
    assert result.linked is False
    assert result.identity_link_id is None
    assert result.identity_status is None
    assert result.identity_method is None
    assert result.canonical_competitor_id is None
    assert result.observations == ()


async def test_active_explicit_link_exposes_matching_provider_evidence(session):
    sport = await add(
        session,
        transfers.Sport,
        slug=f"football-{uuid.uuid4().hex}",
        name="Football",
    )
    source = await add(
        session,
        transfers.SportsDataSource,
        slug=f"stats-{uuid.uuid4().hex}",
        name="Statistics Provider",
    )
    canonical = await transfers.canonical(session, sport)
    provider_athlete = await add(
        session,
        transfers.SportsCompetitor,
        sport_id=sport.id,
        source_id=source.id,
        external_id="provider-player-1",
        name="Provider Athlete",
        competitor_type="athlete",
        canonical_competitor_id=canonical.id,
    )
    human_athlete = await transfers.human(session, sport)

    link = await transfers.SMS24TransfersRepository(session).link_athlete(
        athlete_id=human_athlete.id,
        canonical_competitor_id=canonical.id,
        method="athlete_claim",
        established_by="athlete",
        evidence_reference="claim:test",
        status="declared",
    )

    observation = await add(
        session,
        statistics.Observation,
        sport_id=sport.id,
        source_id=source.id,
        observation_key=f"evidence-{uuid.uuid4().hex}",
        external_id=f"stat-{uuid.uuid4().hex}",
        athlete_external_id=provider_athlete.external_id,
        athlete_name="Provider Athlete",
        athlete_competitor_id=provider_athlete.id,
        scope="season",
        period_label="2026",
        metrics_json={"appearances": 12, "goals": 4},
        metadata_json={"origin": "provider"},
        fetched_at=statistics.NOW,
    )

    result = await AthleteStatisticsEvidenceReader(session=session).read(
        athlete_id=human_athlete.id,
    )

    assert result.linked is True
    assert result.identity_link_id == link.id
    assert result.identity_status == "declared"
    assert result.identity_method == "athlete_claim"
    assert result.canonical_competitor_id == canonical.id
    assert len(result.observations) == 1

    evidence = result.observations[0]
    assert evidence.observation_id == observation.id
    assert evidence.provider_competitor_id == provider_athlete.id
    assert evidence.source_id == source.id
    assert evidence.sport_id == sport.id
    assert evidence.athlete_external_id == "provider-player-1"
    assert evidence.scope == "season"
    assert evidence.period_label == "2026"
    assert evidence.metrics == {"appearances": 12, "goals": 4}
    assert evidence.metadata == {"origin": "provider"}


async def test_mismatched_provider_identity_cannot_leak_into_human_profile(session):
    sport = await add(
        session,
        transfers.Sport,
        slug=f"football-{uuid.uuid4().hex}",
        name="Football",
    )
    source = await add(
        session,
        transfers.SportsDataSource,
        slug=f"stats-primary-{uuid.uuid4().hex}",
        name="Primary Statistics Provider",
    )
    other_source = await add(
        session,
        transfers.SportsDataSource,
        slug=f"stats-other-{uuid.uuid4().hex}",
        name="Other Statistics Provider",
    )
    canonical = await transfers.canonical(session, sport)
    provider_athlete = await add(
        session,
        transfers.SportsCompetitor,
        sport_id=sport.id,
        source_id=source.id,
        external_id="real-provider-player",
        name="Provider Athlete",
        competitor_type="athlete",
        canonical_competitor_id=canonical.id,
    )
    human_athlete = await transfers.human(session, sport)

    await transfers.SMS24TransfersRepository(session).link_athlete(
        athlete_id=human_athlete.id,
        canonical_competitor_id=canonical.id,
        method="athlete_claim",
        established_by="athlete",
        evidence_reference="claim:anti-leak",
        status="declared",
    )

    await add(
        session,
        statistics.Observation,
        sport_id=sport.id,
        source_id=other_source.id,
        observation_key=f"wrong-source-{uuid.uuid4().hex}",
        external_id=f"wrong-source-stat-{uuid.uuid4().hex}",
        athlete_external_id=provider_athlete.external_id,
        athlete_competitor_id=provider_athlete.id,
        scope="season",
        metrics_json={"goals": 99},
        metadata_json={},
        fetched_at=statistics.NOW,
    )
    await add(
        session,
        statistics.Observation,
        sport_id=sport.id,
        source_id=source.id,
        observation_key=f"wrong-athlete-{uuid.uuid4().hex}",
        external_id=f"wrong-athlete-stat-{uuid.uuid4().hex}",
        athlete_external_id="different-provider-player",
        athlete_competitor_id=provider_athlete.id,
        scope="season",
        metrics_json={"goals": 88},
        metadata_json={},
        fetched_at=statistics.NOW,
    )

    result = await AthleteStatisticsEvidenceReader(session=session).read(
        athlete_id=human_athlete.id,
    )

    assert result.linked is True
    assert result.canonical_competitor_id == canonical.id
    assert result.observations == ()


async def test_ended_identity_link_exposes_no_provider_evidence(session):
    sport = await add(
        session,
        transfers.Sport,
        slug=f"football-{uuid.uuid4().hex}",
        name="Football",
    )
    source = await add(
        session,
        transfers.SportsDataSource,
        slug=f"stats-ended-{uuid.uuid4().hex}",
        name="Statistics Provider",
    )
    canonical = await transfers.canonical(session, sport)
    provider_athlete = await add(
        session,
        transfers.SportsCompetitor,
        sport_id=sport.id,
        source_id=source.id,
        external_id="ended-provider-player",
        name="Provider Athlete",
        competitor_type="athlete",
        canonical_competitor_id=canonical.id,
    )
    human_athlete = await transfers.human(session, sport)

    link = await transfers.SMS24TransfersRepository(session).link_athlete(
        athlete_id=human_athlete.id,
        canonical_competitor_id=canonical.id,
        method="athlete_claim",
        established_by="athlete",
        evidence_reference="claim:ended",
        status="declared",
    )

    await add(
        session,
        statistics.Observation,
        sport_id=sport.id,
        source_id=source.id,
        observation_key=f"ended-{uuid.uuid4().hex}",
        external_id=f"ended-stat-{uuid.uuid4().hex}",
        athlete_external_id=provider_athlete.external_id,
        athlete_competitor_id=provider_athlete.id,
        scope="season",
        metrics_json={"appearances": 20},
        metadata_json={},
        fetched_at=statistics.NOW,
    )

    link.ended_at = link.created_at
    await session.flush()

    result = await AthleteStatisticsEvidenceReader(session=session).read(
        athlete_id=human_athlete.id,
    )

    assert result.linked is False
    assert result.identity_link_id is None
    assert result.identity_status is None
    assert result.identity_method is None
    assert result.canonical_competitor_id is None
    assert result.observations == ()


async def test_other_canonical_athlete_evidence_is_excluded(session):
    sport = await add(
        session,
        transfers.Sport,
        slug=f"football-{uuid.uuid4().hex}",
        name="Football",
    )
    source = await add(
        session,
        transfers.SportsDataSource,
        slug=f"stats-isolation-{uuid.uuid4().hex}",
        name="Statistics Provider",
    )

    linked_canonical = await transfers.canonical(session, sport)
    other_canonical = await transfers.canonical(session, sport)

    linked_provider_athlete = await add(
        session,
        transfers.SportsCompetitor,
        sport_id=sport.id,
        source_id=source.id,
        external_id="linked-player",
        name="Linked Provider Athlete",
        competitor_type="athlete",
        canonical_competitor_id=linked_canonical.id,
    )
    other_provider_athlete = await add(
        session,
        transfers.SportsCompetitor,
        sport_id=sport.id,
        source_id=source.id,
        external_id="other-player",
        name="Other Provider Athlete",
        competitor_type="athlete",
        canonical_competitor_id=other_canonical.id,
    )

    human_athlete = await transfers.human(session, sport)
    await transfers.SMS24TransfersRepository(session).link_athlete(
        athlete_id=human_athlete.id,
        canonical_competitor_id=linked_canonical.id,
        method="athlete_claim",
        established_by="athlete",
        evidence_reference="claim:canonical-isolation",
        status="declared",
    )

    expected = await add(
        session,
        statistics.Observation,
        sport_id=sport.id,
        source_id=source.id,
        observation_key=f"linked-{uuid.uuid4().hex}",
        external_id=f"linked-stat-{uuid.uuid4().hex}",
        athlete_external_id=linked_provider_athlete.external_id,
        athlete_competitor_id=linked_provider_athlete.id,
        scope="season",
        metrics_json={"goals": 7},
        metadata_json={},
        fetched_at=statistics.NOW,
    )
    await add(
        session,
        statistics.Observation,
        sport_id=sport.id,
        source_id=source.id,
        observation_key=f"other-{uuid.uuid4().hex}",
        external_id=f"other-stat-{uuid.uuid4().hex}",
        athlete_external_id=other_provider_athlete.external_id,
        athlete_competitor_id=other_provider_athlete.id,
        scope="season",
        metrics_json={"goals": 99},
        metadata_json={},
        fetched_at=statistics.NOW,
    )

    result = await AthleteStatisticsEvidenceReader(session=session).read(
        athlete_id=human_athlete.id,
    )

    assert result.linked is True
    assert result.canonical_competitor_id == linked_canonical.id
    assert [item.observation_id for item in result.observations] == [expected.id]
    assert result.observations[0].metrics == {"goals": 7}


async def test_reading_provider_evidence_never_creates_athlete_performance(session):
    sport = await add(
        session,
        transfers.Sport,
        slug=f"football-{uuid.uuid4().hex}",
        name="Football",
    )
    source = await add(
        session,
        transfers.SportsDataSource,
        slug=f"stats-readonly-{uuid.uuid4().hex}",
        name="Statistics Provider",
    )
    canonical = await transfers.canonical(session, sport)
    provider_athlete = await add(
        session,
        transfers.SportsCompetitor,
        sport_id=sport.id,
        source_id=source.id,
        external_id="readonly-provider-player",
        name="Provider Athlete",
        competitor_type="athlete",
        canonical_competitor_id=canonical.id,
    )
    human_athlete = await transfers.human(session, sport)

    await transfers.SMS24TransfersRepository(session).link_athlete(
        athlete_id=human_athlete.id,
        canonical_competitor_id=canonical.id,
        method="athlete_claim",
        established_by="athlete",
        evidence_reference="claim:readonly",
        status="declared",
    )

    await add(
        session,
        statistics.Observation,
        sport_id=sport.id,
        source_id=source.id,
        observation_key=f"readonly-{uuid.uuid4().hex}",
        external_id=f"readonly-stat-{uuid.uuid4().hex}",
        athlete_external_id=provider_athlete.external_id,
        athlete_competitor_id=provider_athlete.id,
        scope="season",
        metrics_json={"appearances": 15, "goals": 5},
        metadata_json={},
        fetched_at=statistics.NOW,
    )

    before = await statistics.count(session, statistics.AthletePerformance)

    result = await AthleteStatisticsEvidenceReader(session=session).read(
        athlete_id=human_athlete.id,
    )

    after = await statistics.count(session, statistics.AthletePerformance)

    assert result.linked is True
    assert len(result.observations) == 1
    assert before == 0
    assert after == before


async def test_invalid_athlete_id_is_rejected(session):
    reader = AthleteStatisticsEvidenceReader(session=session)

    with pytest.raises(ValueError, match="athlete_id must be a UUID"):
        await reader.read(athlete_id="not-a-uuid")


async def test_provider_evidence_is_ordered_newest_first(session):
    from datetime import timedelta

    sport = await add(
        session,
        transfers.Sport,
        slug=f"football-{uuid.uuid4().hex}",
        name="Football",
    )
    source = await add(
        session,
        transfers.SportsDataSource,
        slug=f"stats-order-{uuid.uuid4().hex}",
        name="Statistics Provider",
    )
    canonical = await transfers.canonical(session, sport)
    provider_athlete = await add(
        session,
        transfers.SportsCompetitor,
        sport_id=sport.id,
        source_id=source.id,
        external_id="ordered-player",
        name="Ordered Provider Athlete",
        competitor_type="athlete",
        canonical_competitor_id=canonical.id,
    )
    human_athlete = await transfers.human(session, sport)

    await transfers.SMS24TransfersRepository(session).link_athlete(
        athlete_id=human_athlete.id,
        canonical_competitor_id=canonical.id,
        method="athlete_claim",
        established_by="athlete",
        evidence_reference="claim:ordering",
        status="declared",
    )

    older = await add(
        session,
        statistics.Observation,
        sport_id=sport.id,
        source_id=source.id,
        observation_key=f"older-{uuid.uuid4().hex}",
        external_id=f"older-stat-{uuid.uuid4().hex}",
        athlete_external_id=provider_athlete.external_id,
        athlete_competitor_id=provider_athlete.id,
        scope="season",
        metrics_json={"goals": 3},
        metadata_json={},
        fetched_at=statistics.NOW,
    )
    newer = await add(
        session,
        statistics.Observation,
        sport_id=sport.id,
        source_id=source.id,
        observation_key=f"newer-{uuid.uuid4().hex}",
        external_id=f"newer-stat-{uuid.uuid4().hex}",
        athlete_external_id=provider_athlete.external_id,
        athlete_competitor_id=provider_athlete.id,
        scope="season",
        metrics_json={"goals": 4},
        metadata_json={},
        fetched_at=statistics.NOW + timedelta(minutes=5),
    )

    result = await AthleteStatisticsEvidenceReader(session=session).read(
        athlete_id=human_athlete.id,
    )

    assert [item.observation_id for item in result.observations] == [
        newer.id,
        older.id,
    ]
