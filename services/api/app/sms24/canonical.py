"""Canonical identity helpers for SMS24 cross-provider fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
import unicodedata


@dataclass(frozen=True, slots=True)
class CanonicalFixtureCandidate:
    """Provider-independent information used to identify a real fixture."""

    sport_slug: str
    starts_at: datetime
    participants: list[str]
    competition_name: str | None = None


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""

    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _normalize_starts_at(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "Canonical fixture starts_at must be timezone-aware"
        )

    return (
        value.astimezone(timezone.utc)
        .replace(second=0, microsecond=0)
        .isoformat()
    )


def build_canonical_fixture_key(
    candidate: CanonicalFixtureCandidate,
) -> str:
    """Build a deterministic provider-independent fixture identity key."""

    sport = _normalize_text(candidate.sport_slug)

    participants = sorted(
        _normalize_text(participant)
        for participant in candidate.participants
        if _normalize_text(participant)
    )

    if not sport:
        raise ValueError(
            "Canonical fixture requires a sport slug"
        )

    if len(participants) < 2:
        raise ValueError(
            "Canonical fixture requires at least two participants"
        )

    starts_at = _normalize_starts_at(candidate.starts_at)

    # Competition is deliberately not part of the hard identity.
    # Providers frequently use different competition labels for the
    # same real-world event. It remains useful metadata for matching,
    # validation and later confidence scoring.
    identity = "|".join(
        [
            sport,
            starts_at,
            *participants,
        ]
    )

    digest = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()

    return f"sms24:{digest}"


def _normalized_participants(
    candidate: CanonicalFixtureCandidate,
) -> tuple[str, ...]:
    participants = tuple(
        sorted(
            normalized
            for participant in candidate.participants
            if (normalized := _normalize_text(participant))
        )
    )

    if len(participants) < 2:
        raise ValueError(
            "Canonical fixture requires at least two participants"
        )

    return participants


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "Canonical fixture starts_at must be timezone-aware"
        )

    return value.astimezone(timezone.utc)


def fixtures_are_same_event(
    first: CanonicalFixtureCandidate,
    second: CanonicalFixtureCandidate,
    *,
    tolerance_minutes: int = 5,
) -> bool:
    """Return whether two provider fixtures represent the same real event."""

    if tolerance_minutes < 0:
        raise ValueError(
            "tolerance_minutes must be non-negative"
        )

    first_sport = _normalize_text(first.sport_slug)
    second_sport = _normalize_text(second.sport_slug)

    if not first_sport or not second_sport:
        raise ValueError(
            "Canonical fixture requires a sport slug"
        )

    if first_sport != second_sport:
        return False

    if (
        _normalized_participants(first)
        != _normalized_participants(second)
    ):
        return False

    first_time = _utc_datetime(first.starts_at)
    second_time = _utc_datetime(second.starts_at)

    delta_seconds = abs(
        (first_time - second_time).total_seconds()
    )

    return delta_seconds <= tolerance_minutes * 60


def build_participant_signature(
    candidate: CanonicalFixtureCandidate,
) -> str:
    """Build a deterministic SHA-256 signature from normalized participants."""

    participants = _normalized_participants(candidate)

    identity = "|".join(participants)

    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()
