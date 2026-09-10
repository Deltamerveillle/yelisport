"""Tests for SMS24 canonical cross-provider fixture identity."""

from datetime import datetime, timedelta, timezone

import pytest

from app.sms24.canonical import (
    CanonicalFixtureCandidate,
    build_canonical_fixture_key,
)


NOW = datetime(2026, 9, 10, 20, 0, tzinfo=timezone.utc)


def make_candidate(
    *,
    sport_slug="football",
    home="ASEC Mimosas",
    away="Africa Sports",
    starts_at=NOW,
    competition="Ligue 1 Côte d'Ivoire",
):
    return CanonicalFixtureCandidate(
        sport_slug=sport_slug,
        competition_name=competition,
        starts_at=starts_at,
        participants=[home, away],
    )


def test_same_match_from_two_providers_has_same_canonical_key():
    api_football = make_candidate(
        home="ASEC Mimosas",
        away="Africa Sports",
    )

    sportmonks = make_candidate(
        home="ASEC Mimosas",
        away="Africa Sports",
    )

    assert (
        build_canonical_fixture_key(api_football)
        == build_canonical_fixture_key(sportmonks)
    )


def test_different_match_has_different_canonical_key():
    first = make_candidate(
        home="ASEC Mimosas",
        away="Africa Sports",
    )

    second = make_candidate(
        home="Stella Club",
        away="SOA",
    )

    assert (
        build_canonical_fixture_key(first)
        != build_canonical_fixture_key(second)
    )


def test_same_teams_far_apart_in_time_are_not_same_fixture():
    first = make_candidate()

    second = make_candidate(
        starts_at=NOW + timedelta(days=7),
    )

    assert (
        build_canonical_fixture_key(first)
        != build_canonical_fixture_key(second)
    )


def test_provider_text_variations_do_not_change_canonical_key():
    first = make_candidate(
        home="ASEC Mimosas",
        away="Africa Sports",
    )

    second = make_candidate(
        sport_slug="FOOTBALL",
        home="  ASEC   MIMOSAS ",
        away="AFRICA SPORTS",
        competition="Ligue 1 Cote d Ivoire",
    )

    assert (
        build_canonical_fixture_key(first)
        == build_canonical_fixture_key(second)
    )


def test_participant_order_does_not_change_canonical_key():
    first = make_candidate(
        home="ASEC Mimosas",
        away="Africa Sports",
    )

    second = make_candidate(
        home="Africa Sports",
        away="ASEC Mimosas",
    )

    assert (
        build_canonical_fixture_key(first)
        == build_canonical_fixture_key(second)
    )


def test_equivalent_instants_in_different_timezones_have_same_key():
    utc_candidate = make_candidate(
        starts_at=datetime(
            2026, 9, 10, 20, 0,
            tzinfo=timezone.utc,
        )
    )

    abidjan_candidate = make_candidate(
        starts_at=datetime(
            2026, 9, 10, 20, 0,
            tzinfo=timezone(timedelta(hours=0)),
        )
    )

    assert (
        build_canonical_fixture_key(utc_candidate)
        == build_canonical_fixture_key(abidjan_candidate)
    )


def test_naive_datetime_is_rejected():
    candidate = make_candidate(
        starts_at=datetime(2026, 9, 10, 20, 0),
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        build_canonical_fixture_key(candidate)


from app.sms24.canonical import fixtures_are_same_event


def test_same_fixture_with_small_start_time_drift_matches():
    first = make_candidate(
        starts_at=NOW,
    )

    second = make_candidate(
        starts_at=NOW + timedelta(minutes=3),
    )

    assert fixtures_are_same_event(
        first,
        second,
        tolerance_minutes=5,
    )


def test_same_fixture_outside_time_tolerance_does_not_match():
    first = make_candidate(
        starts_at=NOW,
    )

    second = make_candidate(
        starts_at=NOW + timedelta(minutes=10),
    )

    assert not fixtures_are_same_event(
        first,
        second,
        tolerance_minutes=5,
    )


def test_different_participants_never_match_even_with_same_time():
    first = make_candidate(
        home="ASEC Mimosas",
        away="Africa Sports",
    )

    second = make_candidate(
        home="Stella Club",
        away="SOA",
    )

    assert not fixtures_are_same_event(
        first,
        second,
        tolerance_minutes=5,
    )


def test_different_sport_never_matches():
    first = make_candidate(
        sport_slug="football",
    )

    second = make_candidate(
        sport_slug="basketball",
    )

    assert not fixtures_are_same_event(
        first,
        second,
        tolerance_minutes=5,
    )


def test_participant_signature_is_provider_independent():
    from app.sms24.canonical import (
        CanonicalFixtureCandidate,
        build_participant_signature,
    )

    first = CanonicalFixtureCandidate(
        sport_slug="football",
        starts_at=NOW,
        participants=[
            "  ASEC Mimosas ",
            "Stade d'Abidjan",
        ],
    )

    second = CanonicalFixtureCandidate(
        sport_slug="football",
        starts_at=NOW,
        participants=[
            "STADE D ABIDJAN",
            "asec   mimosas",
        ],
    )

    assert (
        build_participant_signature(first)
        == build_participant_signature(second)
    )


def test_participant_signature_ignores_participant_order():
    from app.sms24.canonical import (
        CanonicalFixtureCandidate,
        build_participant_signature,
    )

    first = CanonicalFixtureCandidate(
        sport_slug="football",
        starts_at=NOW,
        participants=["ASEC Mimosas", "Africa Sports"],
    )

    second = CanonicalFixtureCandidate(
        sport_slug="football",
        starts_at=NOW,
        participants=["Africa Sports", "ASEC Mimosas"],
    )

    assert (
        build_participant_signature(first)
        == build_participant_signature(second)
    )


def test_participant_signature_is_sha256_length():
    from app.sms24.canonical import (
        CanonicalFixtureCandidate,
        build_participant_signature,
    )

    candidate = CanonicalFixtureCandidate(
        sport_slug="football",
        starts_at=NOW,
        participants=["ASEC Mimosas", "Africa Sports"],
    )

    signature = build_participant_signature(candidate)

    assert len(signature) == 64
    assert all(
        character in "0123456789abcdef"
        for character in signature
    )
