"""GNews contract tests: MockTransport only, no provider or publisher network."""

import logging

import httpx
import pytest

from app.core.config import Settings
from app.sms24.news_runtime import build_sms24_news_registry
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.gnews import GNewsError, GNewsProvider

KEY = "SUPER-SECRET-GNEWS-KEY"


def article(**changes):
    row = {
        "id": "provider-id-not-used",
        "title": "Athletics news",
        "description": "Source-provided short excerpt",
        "content": "FULL CONTENT MUST NEVER BE STORED",
        "url": "https://publisher.example/article?edition=one",
        "image": "https://publisher.example/image.jpg",
        "publishedAt": "2026-09-13T12:30:00Z",
        "lang": "en",
        "source": {"name": "Publisher", "country": "gb", "url": "https://publisher.example"},
    }
    return row | changes


def payload(*articles):
    return {"totalArticles": len(articles), "articles": list(articles)}


@pytest.mark.parametrize("key", [None, "", " "])
def test_runtime_without_key(key):
    settings = Settings(_env_file=None, sms24_gnews_api_key=key)
    assert build_sms24_news_registry(settings).all() == []


def test_runtime_registers_configured_provider_without_database():
    settings = Settings(_env_file=None, sms24_gnews_api_key=KEY)
    registry = build_sms24_news_registry(settings, query="tennis")
    provider = registry.get("gnews")
    assert isinstance(provider, GNewsProvider)
    assert provider.slug == "gnews" and provider.name == "GNews"
    assert KEY not in repr(settings) + repr(provider) + repr(registry)


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 1, 3])
async def test_mapping_and_only_search_request(count, caplog):
    requests = []

    def handle(request):
        requests.append(request)
        assert request.url.host == "gnews.io"
        assert request.url.path == "/api/v4/search"
        assert KEY not in str(request.url)
        assert request.headers["X-Api-Key"] == KEY
        assert "apikey" not in request.url.params
        assert request.url.params["truncate"] == "content"
        assert "expand" not in request.url.params
        assert request.url.params["q"] == "athletics"
        return httpx.Response(200, json=payload(*(article() for _ in range(count))))

    caplog.set_level(logging.DEBUG)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = GNewsProvider(api_key=KEY, query="athletics", client=client)
        health = await provider.check_health()
        assert health.is_healthy and requests == []
        result = await provider.fetch_news()
    assert len(requests) == 1 and len(result.articles) == count
    assert result.fetched_at.utcoffset() is not None
    for row in result.articles:
        assert row.title == "Athletics news"
        assert row.excerpt == "Source-provided short excerpt"
        assert row.source_url.endswith("?edition=one")
        assert row.publisher_name == "Publisher" and row.language_code == "en"
        assert row.published_at.utcoffset() is not None
        assert row.image_url == "https://publisher.example/image.jpg"
        assert row.external_id is row.image_credit is row.provider_updated_at is None
        assert row.news_type is row.source_category is None
        assert row.publication_status == "pending"
        assert row.sport_ids == row.canonical_competition_ids == ()
        assert row.canonical_competitor_ids == row.country_ids == ()
    assert "FULL CONTENT" not in repr(result)
    assert KEY not in repr(result) + caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("language", [None, "fr"])
async def test_missing_optional_metadata(language):
    row = article(image=None, description=None, publishedAt=None, lang=None, source=None)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload(row)))
    ) as client:
        result = await GNewsProvider(api_key=KEY, client=client).search("tennis", language=language)
    mapped = result.articles[0]
    assert (
        mapped.image_url is mapped.excerpt is mapped.published_at is mapped.publisher_name is None
    )
    assert mapped.language_code == language


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"url": "javascript:bad"},
        {"url": "https://example.org/?apikey=secret"},
        {"title": ""},
        {"description": "x" * 1001},
        {"publishedAt": "2026-09-13T12:00:00"},
        {"image": "not-a-url"},
        {"source": "bad"},
        {"lang": 123},
        {"title": KEY},
    ],
)
async def test_invalid_article_rejected(changes):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload(article(**changes)))
        )
    ) as client:
        with pytest.raises(GNewsError, match="gnews_invalid_payload") as caught:
            await GNewsProvider(api_key=KEY, client=client).fetch_news()
    assert KEY not in str(caught.value) + repr(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {},
        {"articles": []},
        {"articles": [], "totalArticles": -1},
        {"articles": [None], "totalArticles": 1},
        {"errors": [KEY]},
        {"articles": {}, "totalArticles": 0},
    ],
)
async def test_invalid_payload(body):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    ) as client:
        with pytest.raises(GNewsError):
            await GNewsProvider(api_key=KEY, client=client).fetch_news()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,code",
    [
        (401, "provider_access_restricted"),
        (403, "provider_access_restricted"),
        (429, "gnews_rate_limited"),
        (500, "gnews_server_error"),
        (503, "gnews_server_error"),
        (400, "gnews_http_error"),
        (302, "gnews_http_error"),
        ("json", "gnews_invalid_json"),
        ("payload", "gnews_invalid_payload"),
        ("timeout", "gnews_timeout"),
        ("network", "gnews_network_error"),
    ],
)
async def test_safe_failures(failure, code, caplog):
    calls = []

    def handle(request):
        calls.append(request)
        assert request.headers["X-Api-Key"] == KEY
        assert "apikey" not in request.url.params
        assert KEY not in str(request.url)
        if failure == "timeout":
            raise httpx.ReadTimeout(KEY, request=request)
        if failure == "network":
            raise httpx.ConnectError(KEY, request=request)
        if failure == "payload":
            return httpx.Response(200, json={"errors": [KEY]})
        return httpx.Response(
            200 if failure == "json" else failure,
            text=KEY,
            headers={"Location": "https://publisher.example"},
        )

    caplog.set_level(logging.DEBUG)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError) as caught:
            await GNewsProvider(api_key=KEY, client=client).fetch_news()
    assert str(caught.value) == code
    if failure in (401, 403):
        assert isinstance(caught.value, ProviderAccessRestrictedError)
        assert caught.value.status_code == failure
    assert KEY not in str(caught.value) + repr(caught.value) + caplog.text
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"query": ""},
        {"query": KEY},
        {"query": "x", "limit": 0},
        {"query": "x", "language": "England"},
    ],
)
async def test_invalid_search_never_requests(kwargs):
    def unexpected(request):
        pytest.fail("Invalid arguments must not make a request")

    async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as client:
        with pytest.raises(GNewsError):
            await GNewsProvider(api_key=KEY, client=client).search(**kwargs)
