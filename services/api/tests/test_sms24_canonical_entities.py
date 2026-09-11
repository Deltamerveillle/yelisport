"""Exact normalization and deterministic entity identity unit tests."""

import pytest

from app.sms24.canonical_entities import (
    build_canonical_competition_key,
    build_canonical_competitor_key,
    normalize_identity_text,
    normalize_jurisdiction,
    normalize_season_label,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  Côte—d’Ivoire  ", "cote d ivoire"),
        ("ST.  Mirren", "st mirren"),
        ("Ｓｅａｓｏｎ ２０２６", "season 2026"),
        ("Straße", "strasse"),
        ("東京 東京", "東京 東京"),
        (None, ""),
        ("Primera División", "primera division"),
    ],
)
def test_normalize_identity_text(value, expected):
    assert normalize_identity_text(value) == expected
    assert normalize_identity_text(expected) == expected


def test_competition_key_determinism_and_boundaries():
    key = build_canonical_competition_key("football", "Premier League", "GB")
    assert key == build_canonical_competition_key("FOOTBALL", "PREMIER  LEAGUE", "gb")
    assert key.startswith("sms24:competition:")
    assert len(key.rsplit(":", 1)[1]) == 64
    for sport, name, country in [
        ("rugby", "Premier League", "GB"),
        ("football", "Premier Division", "GB"),
        ("football", "Premier League", "IE"),
    ]:
        assert key != build_canonical_competition_key(sport, name, country)
    with pytest.raises(ValueError):
        build_canonical_competition_key("football", "League")


def test_competitor_key_determinism_and_no_aliases():
    key = build_canonical_competitor_key("football", "team", "St. Mirren", "GB")
    assert key == build_canonical_competitor_key("football", "team", "ST Mirren", "gb")
    assert key.startswith("sms24:competitor:")
    for sport, kind, name, country in [
        ("rugby", "team", "St. Mirren", "GB"),
        ("football", "selection", "St. Mirren", "GB"),
        ("football", "team", "St. Mirren", "IE"),
        ("football", "team", "Saint Mirren", "GB"),
    ]:
        assert key != build_canonical_competitor_key(sport, kind, name, country)
    assert build_canonical_competitor_key("football", "team", "PSG", "GB") != (
        build_canonical_competitor_key("football", "team", "Paris Saint-Germain", "GB")
    )
    assert build_canonical_competitor_key("football", "team", "東京", "GB") != (
        build_canonical_competitor_key("football", "team", "大阪", "GB")
    )


@pytest.mark.parametrize("kind", ["team", "athlete", "pair", "selection", "other"])
def test_all_competitor_types(kind):
    assert build_canonical_competitor_key("tennis", kind, "Participant", "GB")


@pytest.mark.parametrize("label", ["2026", "2026/27", "2026-2027", "Season 2026", "Tour A"])
def test_season_labels_are_opaque(label):
    assert normalize_season_label(label) == normalize_season_label(label.upper())
    assert normalize_season_label(label) != normalize_season_label(label + " B")


def test_invalid_empty_identities_are_rejected():
    with pytest.raises(ValueError):
        build_canonical_competition_key("football", "---")
    with pytest.raises(ValueError):
        build_canonical_competitor_key("football", "club", "A")
    with pytest.raises(ValueError):
        normalize_season_label("---")
    with pytest.raises(ValueError):
        normalize_season_label("a" * 41)


@pytest.mark.parametrize("label", ["Costa-Rica", " COSTA  RICA ", "Costa.Rica"])
def test_jurisdiction_normalization(label):
    assert normalize_jurisdiction(label) == "costa rica"


@pytest.mark.parametrize("kind", ["competition", "competitor"])
def test_scoped_keys_are_stable_and_cannot_cross_contexts(kind):
    def key(source="api-football", external="42", context=None, name="Arsenal"):
        if kind == "competition":
            return build_canonical_competition_key(
                "football",
                name,
                context,
                source_slug=source,
                external_id=external,
            )
        return build_canonical_competitor_key(
            "football",
            "team",
            name,
            context,
            source_slug=source,
            external_id=external,
        )

    assert key() == key()
    assert key() == key(name="Changed display name")
    assert key() != key(external="9419")
    assert key() != key(source="sportmonks")
    assert key(external="A-B") != key(external="A B")
    assert key(external="a") != key(external="A")
    assert key() != key(context="GB")
    assert key(context="GB") == key(source="sportmonks", external="999", context="gb")
