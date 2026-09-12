"""Local News contract validation; no HTTP adapters or network access."""

import uuid
from datetime import UTC, datetime

import pytest

from app.sms24.providers.news import (
    ProviderNewsArticle,
    ProviderNewsResult,
    build_news_observation_key,
    normalize_news_url,
)

NOW = datetime(2026, 9, 12, tzinfo=UTC)


def article(**kwargs):
    return ProviderNewsArticle(
        **{"title": "Un talent à découvrir", "source_url": "https://news.test/a", **kwargs}
    )


def test_nullable_contract_and_no_implicit_sport():
    item = article()
    assert item.sport_ids == item.country_ids == ()
    for name in (
        "external_id",
        "excerpt",
        "published_at",
        "language_code",
        "image_url",
        "image_credit",
        "news_type",
        "source_category",
        "provider_updated_at",
        "publisher_name",
    ):
        assert getattr(item, name) is None
    assert item.publication_status == "pending"
    result = ProviderNewsResult(fetched_at=NOW, articles=(item,))
    assert result.articles == (item,)
    assert result.fetched_at.utcoffset() is not None


@pytest.mark.parametrize("field", ["published_at", "provider_updated_at"])
def test_article_dates_require_timezone(field):
    with pytest.raises(ValueError, match="timezone-aware"):
        article(**{field: datetime(2026, 9, 12)})
    assert getattr(article(**{field: NOW}), field) == NOW


@pytest.mark.parametrize("timestamp", [None, datetime(2026, 9, 12), "2026-09-12"])
def test_fetched_at_required_and_aware(timestamp):
    with pytest.raises(ValueError, match="timezone-aware"):
        ProviderNewsResult(fetched_at=timestamp)


def test_observation_identity_is_deterministic_scoped_and_not_title_based():
    key = build_news_observation_key("42", "https://news.test/a")
    assert key == build_news_observation_key("42", "https://news.test/renamed")
    assert key != build_news_observation_key("43", "https://news.test/a")
    assert key != build_news_observation_key(None, "https://news.test/a")
    assert key.startswith("sms24:news:") and len(key.rsplit(":", 1)[1]) == 64
    assert build_news_observation_key("A", "https://news.test/a") != build_news_observation_key(
        "a", "https://news.test/a"
    )


def test_url_key_preserves_query_and_path():
    assert (
        normalize_news_url("HTTPS://NEWS.TEST/A?id=1&utm_x=2#section")
        == "https://news.test/A?id=1&utm_x=2"
    )
    base = build_news_observation_key(None, "https://news.test/A?id=1&utm_x=2")
    assert base == build_news_observation_key(None, "HTTPS://NEWS.TEST/A?id=1&utm_x=2#section")
    for url in (
        "https://news.test/A?id=2&utm_x=2",
        "https://news.test/A?id=1",
        "https://news.test/a?id=1&utm_x=2",
    ):
        assert base != build_news_observation_key(None, url)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:private-secret",
        "https://user:private-secret@news.test/a",
        "https://news.test/a?api_key=private-secret",
        "https://news.test:private-secret/a",
        "https://news.test/\nprivate-secret",
        "https://news.test/a?access_token=private-secret",
    ],
)
def test_url_errors_do_not_expose_credentials(url):
    for field in ("source_url", "image_url"):
        with pytest.raises(ValueError) as caught:
            article(**{field: url})
        assert "private-secret" not in str(caught.value)


@pytest.mark.parametrize(
    "values",
    [
        {"title": " "},
        {"external_id": ""},
        {"excerpt": "x" * 1001},
        {"publication_status": "automatic"},
        {"language_code": "not a language"},
        {"sport_ids": ("football",)},
        {"canonical_competitor_ids": ("Rangers",)},
    ],
)
def test_invalid_contract_rejected(values):
    with pytest.raises(ValueError):
        article(**values)


def test_explicit_multisport_and_country_ids():
    sports = (uuid.uuid4(), uuid.uuid4())
    country = uuid.uuid4()
    item = article(sport_ids=sports, country_ids=(country,), language_code="pt-BR")
    assert item.sport_ids == sports and item.country_ids == (country,)
