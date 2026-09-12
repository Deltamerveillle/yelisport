"""Local multisport News contract. No HTTP or fixture-provider dependency.

Identifiers are explicit UUIDs mapped by the caller, never inferred from names.
An adapter must keep its identity strategy stable: external ID when supplied,
otherwise the conservative URL key. Adding an ID later requires explicit reconciliation.
"""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import parse_qsl, urlsplit, urlunsplit

TEXT_LIMITS = {
    "external_id": 160,
    "title": 500,
    "excerpt": 1000,
    "publisher_name": 240,
    "language_code": 40,
    "image_credit": 500,
    "news_type": 80,
    "source_category": 200,
}
LINK_FIELDS = ("sport_ids", "canonical_competition_ids", "canonical_competitor_ids", "country_ids")


def validate_timestamp(value: datetime | None, *, required: bool = False) -> None:
    if value is None and not required:
        return
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("News timestamp must be timezone-aware")


def normalize_news_url(value: str) -> str:
    """Lowercase scheme/authority and omit fragments; preserve path/query exactly.

    Reject credential-bearing URLs rather than persisting a redacted identity.
    This validation performs no network access and is not an HTTP-fetch policy.
    """
    try:
        if not isinstance(value, str) or not value or len(value) > 2048:
            raise ValueError
        if any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
            raise ValueError
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise ValueError
        if parts.username is not None or parts.password is not None:
            raise ValueError
        _ = parts.port  # Reject malformed ports without surfacing the raw URL.
        secret_keys = {
            "key",
            "apikey",
            "api_key",
            "api_token",
            "token",
            "access_token",
            "authorization",
            "password",
            "secret",
            "signature",
            "x-amz-signature",
        }
        if any(key.casefold() in secret_keys for key, _ in parse_qsl(parts.query)):
            raise ValueError
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))
    except (ValueError, TypeError):
        raise ValueError("News URL must be a public HTTP(S) URL without credentials") from None


def build_news_observation_key(external_id: str | None, source_url: str) -> str:
    normalized_url = normalize_news_url(source_url)
    if external_id is not None:
        if not isinstance(external_id, str) or not external_id.strip() or len(external_id) > 160:
            raise ValueError("News external identifier must be a nonempty opaque string")
        parts = ["external_id", external_id]
    else:
        parts = ["url", normalized_url]
    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return "sms24:news:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderNewsArticle:
    title: str
    source_url: str
    external_id: str | None = None
    excerpt: str | None = None
    publisher_name: str | None = None
    published_at: datetime | None = None
    language_code: str | None = None
    image_url: str | None = None
    image_credit: str | None = None
    news_type: str | None = None
    source_category: str | None = None
    provider_updated_at: datetime | None = None
    publication_status: str = "pending"
    sport_ids: tuple[uuid.UUID, ...] = field(default_factory=tuple)
    canonical_competition_ids: tuple[uuid.UUID, ...] = field(default_factory=tuple)
    canonical_competitor_ids: tuple[uuid.UUID, ...] = field(default_factory=tuple)
    country_ids: tuple[uuid.UUID, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        validate_news_article(self)


def validate_news_article(article: ProviderNewsArticle) -> None:
    if not isinstance(article, ProviderNewsArticle):
        raise ValueError("Invalid News article contract")
    for name, limit in TEXT_LIMITS.items():
        value = getattr(article, name)
        if value is not None and (not isinstance(value, str) or len(value) > limit):
            raise ValueError(f"Invalid News {name}")
    if not isinstance(article.title, str) or not article.title.strip():
        raise ValueError("News title is required")
    build_news_observation_key(article.external_id, article.source_url)
    if article.image_url is not None:
        normalize_news_url(article.image_url)
    if article.language_code is not None and not re.fullmatch(
        r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", article.language_code
    ):
        raise ValueError("Invalid News language code")
    if article.publication_status not in ("pending", "published", "withheld"):
        raise ValueError("Invalid News publication status")
    validate_timestamp(article.published_at)
    validate_timestamp(article.provider_updated_at)
    for name in LINK_FIELDS:
        values = getattr(article, name)
        if not isinstance(values, tuple | list) or any(
            not isinstance(v, uuid.UUID) for v in values
        ):
            raise ValueError(f"News {name} must contain explicit UUIDs")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderNewsResult:
    fetched_at: datetime
    articles: tuple[ProviderNewsArticle, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        validate_timestamp(self.fetched_at, required=True)
        if not isinstance(self.articles, tuple | list):
            raise ValueError("News result must contain articles")
        for article in self.articles:
            validate_news_article(article)
