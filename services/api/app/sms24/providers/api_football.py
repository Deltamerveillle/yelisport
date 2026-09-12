"""API-Football provider adapter for SMS24."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any

import httpx

from app.sms24.providers.base import (
    ProviderCompetition,
    ProviderFetchResult,
    ProviderFixture,
    ProviderHealthResult,
    ProviderParticipant,
    SportsDataProvider,
)

from app.sms24.providers.errors import ProviderAccessRestrictedError
from app.sms24.providers.standings import (
    ProviderStandingsRequest, ProviderStandingsResult, validate_standings_request,
)
from app.sms24.providers.standings_normalization import normalize_api_football_standing


class APIFootballProvider(SportsDataProvider):
    """Normalize API-Football fixtures into the SMS24 provider contract."""

    normalize_standing = staticmethod(normalize_api_football_standing)

    slug = "api-football"
    name = "API-Football"

    DEFAULT_BASE_URL = "https://v3.football.api-sports.io"

    STATUS_MAP = {
        "TBD": "scheduled",
        "NS": "scheduled",
        "1H": "live",
        "HT": "live",
        "2H": "live",
        "ET": "live",
        "BT": "live",
        "P": "live",
        "SUSP": "suspended",
        "INT": "suspended",
        "FT": "finished",
        "AET": "finished",
        "PEN": "finished",
        "PST": "postponed",
        "CANC": "cancelled",
        "ABD": "cancelled",
        "AWD": "finished",
        "WO": "finished",
        "LIVE": "live",
    }

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None = None,
        timeout_seconds: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        api_key = api_key.strip()

        if not api_key:
            raise ValueError("API-Football API key is required")

        self.api_key = api_key
        self.base_url = (
            base_url or self.DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = client

    async def fetch_fixtures(
        self,
        *,
        sport_slug: str | None = None,
        starts_from: datetime | None = None,
        starts_until: datetime | None = None,
        live_only: bool = False,
    ) -> ProviderFetchResult:
        if sport_slug not in (None, "football"):
            return ProviderFetchResult(
                fixtures=[],
                fetched_at=datetime.now(timezone.utc),
                raw_count=0,
            )

        params: dict[str, str] = {}

        if live_only:
            params["live"] = "all"
        else:
            if starts_from is not None:
                self._require_timezone_aware(starts_from)

            if starts_until is not None:
                self._require_timezone_aware(starts_until)

            if (
                starts_from is not None
                and starts_until is not None
                and starts_from > starts_until
            ):
                raise ValueError(
                    "starts_from must be before or equal to starts_until"
                )

            if (
                starts_from is not None
                and starts_until is not None
            ):
                if starts_from.date() != starts_until.date():
                    raise ValueError(
                        "API-Football global fixture fetch supports "
                        "one calendar day at a time"
                    )

                params["date"] = starts_from.date().isoformat()

            elif starts_from is not None:
                params["date"] = starts_from.date().isoformat()

            elif starts_until is not None:
                params["date"] = starts_until.date().isoformat()

        payload = await self._get_json(
            "/fixtures",
            params=params,
        )

        raw_response = payload.get("response", [])

        if not isinstance(raw_response, list):
            raise ValueError(
                "API-Football response field must be a list"
            )

        fixtures: list[ProviderFixture] = []

        for item in raw_response:
            fixtures.append(self._normalize_fixture(item))

        return ProviderFetchResult(
            fixtures=fixtures,
            fetched_at=datetime.now(timezone.utc),
            raw_count=len(raw_response),
        )

    async def fetch_standings(
        self, *, season: str, league_external_id: str | None = None,
    ) -> ProviderStandingsResult:
        validate_standings_request(ProviderStandingsRequest(season, league_external_id))
        if league_external_id is None:
            raise ValueError("API-Football standings require league_external_id")
        try:
            payload = await self._get_json(
                "/standings", params={"league": league_external_id, "season": season},
            )
        except ProviderAccessRestrictedError:
            raise
        except Exception:
            # Transport errors and provider error bodies may contain credentials.
            raise RuntimeError("API-Football standings request failed") from None
        response = payload.get("response")
        if not isinstance(response, list):
            raise ValueError("API-Football standings response must be a list")
        rows = []
        for item in response:
            league = item.get("league") if isinstance(item, dict) else None
            if not isinstance(league, dict):
                raise ValueError("API-Football standings league must be an object")
            if str(league.get("id")) != league_external_id or str(league.get("season")) != season:
                raise ValueError("API-Football standings league/season does not match request")
            groups = league.get("standings")
            if not isinstance(groups, list):
                raise ValueError("API-Football standings groups must be a list")
            for group in groups:
                if not isinstance(group, list):
                    raise ValueError("API-Football standings group must be a list")
                for raw_row in group:
                    row = self.normalize_standing(raw_row)
                    row.external_competition_id = str(league["id"])
                    row.external_season_id = str(league["season"])
                    rows.append(row)
        return ProviderStandingsResult(rows=rows, fetched_at=datetime.now(timezone.utc))

    async def check_health(self) -> ProviderHealthResult:
        checked_at = datetime.now(timezone.utc)
        started = time.perf_counter()

        try:
            payload = await self._get_json(
                "/status",
                params={},
            )

            latency_ms = int(
                (time.perf_counter() - started) * 1000
            )

            return ProviderHealthResult(
                is_healthy=True,
                checked_at=checked_at,
                latency_ms=latency_ms,
                message=self._health_message(payload),
            )

        except Exception as exc:
            latency_ms = int(
                (time.perf_counter() - started) * 1000
            )

            return ProviderHealthResult(
                is_healthy=False,
                checked_at=checked_at,
                latency_ms=latency_ms,
                message=str(exc),
            )

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, str],
    ) -> dict[str, Any]:
        headers = {
            "x-apisports-key": self.api_key,
        }

        if self._client is not None:
            response = await self._client.get(
                f"{self.base_url}{path}",
                headers=headers,
                params=params,
                timeout=self.timeout_seconds,
            )
            return self._parse_response(response)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}{path}",
                headers=headers,
                params=params,
                timeout=self.timeout_seconds,
            )

        return self._parse_response(response)

    @staticmethod
    def _parse_response(
        response: httpx.Response,
    ) -> dict[str, Any]:
        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, dict):
            raise ValueError(
                "API-Football payload must be an object"
            )

        errors = payload.get("errors")

        if isinstance(errors, dict) and "plan" in errors:
            raise ProviderAccessRestrictedError()

        if errors:
            raise RuntimeError(
                f"API-Football returned errors: {errors}"
            )

        return payload

    def _normalize_fixture(
        self,
        item: Any,
    ) -> ProviderFixture:
        if not isinstance(item, dict):
            raise ValueError(
                "API-Football fixture item must be an object"
            )

        fixture_data = self._require_dict(
            item,
            "fixture",
        )
        league_data = self._require_dict(
            item,
            "league",
        )
        teams_data = self._require_dict(
            item,
            "teams",
        )

        home = self._require_dict(
            teams_data,
            "home",
        )
        away = self._require_dict(
            teams_data,
            "away",
        )

        goals = item.get("goals") or {}
        score = item.get("score") or {}

        if not isinstance(goals, dict):
            goals = {}

        if not isinstance(score, dict):
            score = {}

        fixture_id = fixture_data.get("id")
        fixture_date = fixture_data.get("date")

        if fixture_id is None:
            raise ValueError(
                "API-Football fixture id is required"
            )

        if not isinstance(fixture_date, str):
            raise ValueError(
                "API-Football fixture date is required"
            )

        starts_at = self._parse_datetime(
            fixture_date
        )

        status_data = fixture_data.get("status") or {}

        if not isinstance(status_data, dict):
            status_data = {}

        status_short = str(
            status_data.get("short") or ""
        ).upper()

        status = self.STATUS_MAP.get(
            status_short,
            "unknown",
        )

        elapsed = status_data.get("elapsed")

        live_clock = None
        if elapsed is not None:
            live_clock = str(elapsed)

        venue_data = fixture_data.get("venue") or {}

        if not isinstance(venue_data, dict):
            venue_data = {}

        venue = venue_data.get("name")
        venue_city = venue_data.get("city")

        if venue and venue_city:
            venue = f"{venue}, {venue_city}"
        elif not venue:
            venue = venue_city

        competition_id = league_data.get("id")
        competition_name = league_data.get("name")

        competition = None

        if (
            competition_id is not None
            and competition_name
        ):
            competition = ProviderCompetition(
                external_id=str(competition_id),
                name=str(competition_name),
                # This field is a sporting jurisdiction label, not an ISO2 field.
                country_code=None,
                jurisdiction_name=(
                    league_data["country"].strip() or None
                    if isinstance(league_data.get("country"), str) else None
                ),
                season=(
                    str(league_data["season"])
                    if league_data.get("season")
                    is not None
                    else None
                ),
                logo_url=league_data.get("logo"),
            )

        home_score = goals.get("home")
        away_score = goals.get("away")

        participants = [
            self._normalize_team(
                home,
                role="home",
                position=0,
                score=home_score,
                result_status=self._result_status(
                    winner=home.get("winner"),
                    fixture_status=status,
                ),
            ),
            self._normalize_team(
                away,
                role="away",
                position=1,
                score=away_score,
                result_status=self._result_status(
                    winner=away.get("winner"),
                    fixture_status=status,
                ),
            ),
        ]

        return ProviderFixture(
            external_id=str(fixture_id),
            sport_slug="football",
            starts_at=starts_at,
            status=status,
            name=(
                f"{participants[0].name} vs "
                f"{participants[1].name}"
            ),
            live_clock=live_clock,
            venue=venue,
            competition=competition,
            participants=participants,
            result={
                "goals": goals,
                "score": score,
            },
            metadata={
                "provider_status": status_short,
                "round": league_data.get("round"),
                "timezone": fixture_data.get(
                    "timezone"
                ),
                "referee": fixture_data.get(
                    "referee"
                ),
            },
        )

    @staticmethod
    def _normalize_team(
        team: dict[str, Any],
        *,
        role: str,
        position: int,
        score: Any,
        result_status: str | None,
    ) -> ProviderParticipant:
        team_id = team.get("id")
        name = team.get("name")

        if team_id is None:
            raise ValueError(
                "API-Football team id is required"
            )

        if not name:
            raise ValueError(
                "API-Football team name is required"
            )

        return ProviderParticipant(
            external_id=str(team_id),
            name=str(name),
            competitor_type="team",
            logo_url=team.get("logo"),
            position=position,
            role=role,
            score={
                "value": score,
            },
            result_status=result_status,
        )

    @staticmethod
    def _result_status(
        *,
        winner: Any,
        fixture_status: str,
    ) -> str | None:
        if fixture_status != "finished":
            return None

        if winner is True:
            return "winner"

        if winner is False:
            return "loser"

        return "draw"

    @staticmethod
    def _normalize_country_code(
        value: Any,
    ) -> str | None:
        if not isinstance(value, str):
            return None

        value = value.strip().upper()

        if len(value) == 2:
            return value

        return None

    @staticmethod
    def _parse_datetime(
        value: str,
    ) -> datetime:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        APIFootballProvider._require_timezone_aware(
            parsed
        )

        return parsed

    @staticmethod
    def _require_timezone_aware(
        value: datetime,
    ) -> None:
        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "datetime must be timezone-aware"
            )

    @staticmethod
    def _require_dict(
        parent: dict[str, Any],
        key: str,
    ) -> dict[str, Any]:
        value = parent.get(key)

        if not isinstance(value, dict):
            raise ValueError(
                f"API-Football field '{key}' "
                "must be an object"
            )

        return value

    @staticmethod
    def _health_message(
        payload: dict[str, Any],
    ) -> str:
        response = payload.get("response")

        if isinstance(response, dict):
            account = response.get("account")

            if isinstance(account, dict):
                firstname = account.get("firstname")
                lastname = account.get("lastname")

                name = " ".join(
                    str(value)
                    for value in (
                        firstname,
                        lastname,
                    )
                    if value
                )

                if name:
                    return f"API-Football account: {name}"

        return "API-Football reachable"
