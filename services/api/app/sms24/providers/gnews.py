"""GNews search adapter. No database writes, publisher requests or full-content expansion.

Docs: https://docs.gnews.io/endpoints/search-endpoint
Authentication: https://docs.gnews.io/authentication explicitly supports both
apikey query parameters and X-Api-Key headers. We use only the documented header
to keep credentials out of request URLs. Health is a local configuration gate;
actual upstream availability is established by fetch_news.
"""

import re
from datetime import UTC, datetime

import httpx
from pydantic import SecretStr

from app.sms24.providers.base import ProviderHealthResult
from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.news import ProviderNewsArticle, ProviderNewsResult
from app.sms24.providers.news_provider import NewsProvider


class GNewsError(RuntimeError):
    """Only internally selected codes are passed here, never upstream text or requests."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class GNewsAccessRestrictedError(ProviderAccessRestrictedError):
    def __init__(self, status_code: int) -> None:
        super().__init__()
        self.status_code = status_code


class GNewsProvider(NewsProvider):
    slug = "gnews"
    name = "GNews"
    SEARCH_URL = "https://gnews.io/api/v4/search"

    def __init__(
        self,
        *,
        api_key: str,
        query: str = "sport",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise GNewsError("gnews_not_configured")
        self._api_key = SecretStr(api_key.strip())
        self._validate_query(query)
        self._query = query
        self._client = client

    def _validate_query(self, query: str) -> None:
        if (
            not isinstance(query, str)
            or not query.strip()
            or len(query) > 200
            or self._api_key.get_secret_value() in query
        ):
            raise GNewsError("gnews_invalid_query")

    async def check_health(self) -> ProviderHealthResult:
        # GNews has no audited dedicated health endpoint. Do not spend another search
        # request or claim that this local check proves remote access/subscription rights.
        return ProviderHealthResult(
            is_healthy=True,
            checked_at=datetime.now(UTC),
            message="local_configuration_ready",
        )

    async def fetch_news(self) -> ProviderNewsResult:
        return await self.search(self._query)

    async def search(
        self,
        query: str,
        *,
        language: str | None = None,
        limit: int = 10,
    ) -> ProviderNewsResult:
        self._validate_query(query)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise GNewsError("gnews_invalid_limit")
        if language is not None and (
            not isinstance(language, str) or not re.fullmatch(r"[a-z]{2}", language)
        ):
            raise GNewsError("gnews_invalid_language")
        params = {"q": query, "max": str(limit), "truncate": "content", "in": "title,description"}
        if language is not None:
            params["lang"] = language
        response = await self._request(params)
        if response.status_code in (401, 403):
            raise GNewsAccessRestrictedError(response.status_code)
        if response.status_code == 429:
            raise GNewsError("gnews_rate_limited")
        if response.status_code >= 500:
            raise GNewsError("gnews_server_error")
        if response.status_code != 200:
            raise GNewsError("gnews_http_error")
        try:
            payload = response.json()
        except (ValueError, UnicodeError):
            raise GNewsError("gnews_invalid_json") from None
        try:
            if not isinstance(payload, dict) or payload.get("errors"):
                raise ValueError
            articles = payload.get("articles")
            total = payload.get("totalArticles")
            if not isinstance(articles, list) or type(total) is not int or total < len(articles):
                raise ValueError
            mapped = tuple(self._article(row, language) for row in articles)
            # A provider must never reflect its credential into persisted/editorial fields.
            if self._api_key.get_secret_value() in repr(mapped):
                raise ValueError
            return ProviderNewsResult(fetched_at=datetime.now(UTC), articles=mapped)
        except (ValueError, TypeError, AttributeError):
            raise GNewsError("gnews_invalid_payload") from None

    async def _request(self, params: dict[str, str]) -> httpx.Response:
        headers = {"X-Api-Key": self._api_key.get_secret_value()}
        try:
            if self._client is not None:
                return await self._client.get(
                    self.SEARCH_URL,
                    params=params,
                    headers=headers,
                    timeout=10.0,
                    follow_redirects=False,
                )
            async with httpx.AsyncClient() as client:
                return await client.get(
                    self.SEARCH_URL,
                    params=params,
                    headers=headers,
                    timeout=10.0,
                    follow_redirects=False,
                )
        except httpx.TimeoutException:
            raise GNewsError("gnews_timeout") from None
        except Exception:
            # Never return HTTPX exceptions: they may carry headers or credential URLs.
            raise GNewsError("gnews_network_error") from None

    @staticmethod
    def _article(row: dict, language: str | None) -> ProviderNewsArticle:
        if not isinstance(row, dict):
            raise ValueError
        publisher = row.get("source")
        if publisher is not None and not isinstance(publisher, dict):
            raise ValueError
        published = row.get("publishedAt")
        if published is not None:
            if not isinstance(published, str):
                raise ValueError
            published = datetime.fromisoformat(published.replace("Z", "+00:00"))
        article_language = row.get("lang")
        if article_language is None:
            article_language = language  # Explicit API language filter, never title inference.
        return ProviderNewsArticle(
            title=row.get("title"),
            source_url=row.get("url"),
            excerpt=row.get("description"),
            publisher_name=publisher.get("name") if publisher else None,
            published_at=published,
            language_code=article_language,
            image_url=row.get("image"),
            # No durable provider-ID policy audited yet: reuse the foundation's URL identity.
            external_id=None,
        )
