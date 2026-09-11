"""Exact, provider-independent SMS24 competition, competitor and season identity.

Only superficial text differences are normalized; no aliases or fuzzy matching.
Fixture identity deliberately continues to use its existing helpers.
"""

import hashlib
import json
import unicodedata


def normalize_identity_text(value: str | None) -> str:
    """Strip accents and punctuation while retaining Unicode letters and digits."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    unaccented = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in unaccented.casefold()).split())


def _build_key(kind: str, parts: list[str]) -> str:
    # Structured encoding keeps component boundaries unambiguous.
    identity = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"sms24:{kind}:{digest}"


def normalize_jurisdiction(value: str | None) -> str:
    """Normalize a sporting label without inferring an ISO country or association."""
    return normalize_identity_text(value)


def _identity_parts(
    sport_slug: str,
    name: str,
    context: str | None,
    source_slug: str | None,
    external_id: str | None,
) -> list[str]:
    sport = normalize_identity_text(sport_slug)
    normalized_name = normalize_identity_text(name)
    if not sport or not normalized_name:
        raise ValueError("Canonical identity requires a normalized sport slug and name")
    normalized_context = normalize_identity_text(context)
    if normalized_context:
        return [sport, "verified_context", normalized_name, normalized_context]
    if not source_slug or not source_slug.strip() or not external_id or not external_id.strip():
        raise ValueError("Provider-scoped identity requires source slug and external id")
    # Provider identifiers are opaque. Never punctuation-normalize or casefold them.
    return [sport, "provider_scoped", source_slug, external_id]


def build_canonical_competition_key(
    sport_slug: str,
    name: str,
    jurisdiction_name: str | None = None,
    *,
    source_slug: str | None = None,
    external_id: str | None = None,
) -> str:
    return _build_key(
        "competition",
        _identity_parts(
            sport_slug,
            name,
            normalize_jurisdiction(jurisdiction_name),
            source_slug,
            external_id,
        ),
    )


def build_canonical_competitor_key(
    sport_slug: str,
    competitor_type: str,
    name: str,
    country_code: str | None = None,
    *,
    source_slug: str | None = None,
    external_id: str | None = None,
) -> str:
    if competitor_type not in {"team", "athlete", "pair", "selection", "other"}:
        raise ValueError(f"Unsupported SMS24 competitor type: {competitor_type}")
    # The provider contract reserves country_code for reliable ISO2 inputs.
    context = country_code.strip() if country_code else None
    if context and (len(context) != 2 or not context.isascii() or not context.isalpha()):
        context = None
    parts = _identity_parts(sport_slug, name, context, source_slug, external_id)
    return _build_key("competitor", [parts[0], competitor_type, *parts[1:]])


def normalize_season_label(label: str) -> str:
    """Normalize opaque season labels without interpreting dates or sport formats."""
    normalized = normalize_identity_text(label)
    if not normalized or len(normalized) > 40:
        raise ValueError("Canonical season requires a normalized label of 1 to 40 characters")
    return normalized
