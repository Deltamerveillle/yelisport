"""Sportmonks Football V3 adapter; coverage is limited to the token's subscription."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from app.sms24.providers.base import (
    ProviderCompetition,
    ProviderFetchResult,
    ProviderFixture,
    ProviderHealthResult,
    ProviderParticipant,
    SportsDataProvider,
)

from app.sms24.providers.standings import (
    ProviderStandingsRequest, ProviderStandingsResult, validate_standings_request,
)
from app.sms24.providers.standings_normalization import normalize_sportmonks_standing


class SportmonksProvider(SportsDataProvider):
    normalize_standing = staticmethod(normalize_sportmonks_standing)

    slug = "sportmonks"
    name = "Sportmonks"
    DEFAULT_BASE_URL = "https://api.sportmonks.com/v3/football"
    INCLUDES = "participants;league.country;season;state;scores;periods;venue"
    # V3 state IDs: https://docs.sportmonks.com/v3/definitions/states
    STATUS_MAP = {
        1: "scheduled", 2: "live", 3: "live", 4: "live", 5: "finished",
        6: "live", 7: "finished", 8: "finished", 9: "live", 10: "postponed",
        11: "suspended", 12: "cancelled", 13: "scheduled", 14: "finished",
        15: "suspended", 16: "scheduled", 17: "finished", 18: "suspended",
        19: "unknown", 20: "cancelled", 21: "live", 22: "live", 25: "live",
        26: "unknown",
    }

    def __init__(
        self, *, api_key: str, base_url: str | None = None,
        timeout_seconds: float = 15.0, max_pages: int = 100,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Sportmonks API key is required")
        if type(max_pages) is not int or max_pages < 1:
            raise ValueError("Sportmonks max_pages must be a positive integer")
        self.api_key = api_key.strip()
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_pages = max_pages
        self._client = client

    async def fetch_fixtures(
        self, *, sport_slug: str | None = None,
        starts_from: datetime | None = None, starts_until: datetime | None = None,
        live_only: bool = False,
    ) -> ProviderFetchResult:
        if sport_slug not in (None, "football"):
            return ProviderFetchResult(fetched_at=datetime.now(timezone.utc))
        day = self._day(starts_from, starts_until)
        path = "/livescores/inplay" if live_only else f"/fixtures/date/{day}"
        params = {"include": self.INCLUDES, "timezone": "UTC"}
        fixtures = []
        seen = set()
        for page in range(1, self.max_pages + 1):
            if not live_only:
                params.update(page=str(page), per_page="50")
            payload = await self._get_json(path, params=params)
            for item in payload["data"]:
                fixture = self._normalize_fixture(item)
                if fixture.external_id in seen:
                    raise ValueError("Sportmonks duplicate fixture in response")
                seen.add(fixture.external_id)
                fixtures.append(fixture)
            if live_only or not self._has_more(payload, page):
                return ProviderFetchResult(
                    fixtures=fixtures, raw_count=len(fixtures),
                    fetched_at=datetime.now(timezone.utc),
                )
        raise RuntimeError("Sportmonks pagination limit exceeded")

    async def fetch_standings(
        self, *, season: str, league_external_id: str | None = None,
    ) -> ProviderStandingsResult:
        validate_standings_request(ProviderStandingsRequest(season, league_external_id))
        if season in {".", ".."}:
            raise ValueError("Sportmonks invalid season identifier")
        path = f"/standings/seasons/{quote(season, safe='')}"
        rows = []
        seen = set()
        for page in range(1, self.max_pages + 1):
            payload = await self._get_json(path, params={
                "include": "participant;details.type;rule.type", "page": str(page), "per_page": "50",
            })
            for raw_row in payload["data"]:
                row = self.normalize_standing(raw_row)
                if row.external_season_id != season or (
                    league_external_id is not None and row.external_competition_id != league_external_id
                ):
                    raise ValueError("Sportmonks standings league/season does not match request")
                if row.external_id in seen:
                    raise ValueError("Sportmonks duplicate standing in response")
                seen.add(row.external_id)
                rows.append(row)
            pagination = payload.get("pagination")
            if pagination is None:
                if page != 1:
                    raise ValueError("Sportmonks standings pagination disappeared")
                return ProviderStandingsResult(
                    rows=rows,
                    fetched_at=datetime.now(timezone.utc),
                )
            if not self._has_more(payload, page):
                return ProviderStandingsResult(
                    rows=rows,
                    fetched_at=datetime.now(timezone.utc),
                )
            if not payload["data"]:
                raise ValueError("Sportmonks empty standings page with more pages")
        raise RuntimeError("Sportmonks standings pagination limit exceeded")

    async def check_health(self) -> ProviderHealthResult:
        checked_at = datetime.now(timezone.utc)
        started = time.perf_counter()
        try:
            await self._get_json(
                f"/fixtures/date/{checked_at.date().isoformat()}",
                params={"per_page": "1", "page": "1", "timezone": "UTC"},
            )
            healthy = True
        except Exception:
            healthy = False
        return ProviderHealthResult(
            is_healthy=healthy, checked_at=checked_at,
            latency_ms=int((time.perf_counter() - started) * 1000),
            message="Sportmonks reachable" if healthy else "Sportmonks unavailable",
        )

    async def _get_json(self, path: str, *, params: dict[str, str]) -> dict[str, Any]:
        # Do not propagate transport errors, response bodies or URLs: they may echo secrets.
        try:
            if self._client is not None:
                response = await self._client.get(
                    f"{self.base_url}{path}", headers={"Authorization": self.api_key},
                    params=params, timeout=self.timeout_seconds, follow_redirects=False,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.base_url}{path}", headers={"Authorization": self.api_key},
                        params=params, timeout=self.timeout_seconds, follow_redirects=False,
                    )
        except Exception:
            raise RuntimeError("Sportmonks request failed") from None
        if not response.is_success:
            raise RuntimeError(f"Sportmonks HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            raise ValueError("Sportmonks invalid JSON") from None
        if (
            not isinstance(payload, dict) or not isinstance(payload.get("data"), list)
            or payload.get("error") or payload.get("errors")
        ):
            raise ValueError("Sportmonks invalid response envelope")
        return payload

    @staticmethod
    def _has_more(payload: dict[str, Any], page: int) -> bool:
        pagination = payload.get("pagination")
        if (
            not isinstance(pagination, dict)
            or type(pagination.get("has_more")) is not bool
            or pagination.get("current_page") != page
        ):
            raise ValueError("Sportmonks invalid pagination")
        # Reconstruct the next request locally; never follow an upstream next_page URL.
        return pagination["has_more"]

    @staticmethod
    def _day(starts_from: datetime | None, starts_until: datetime | None) -> str:
        values = []
        for value in (starts_from, starts_until):
            if value is not None:
                if value.tzinfo is None or value.utcoffset() is None:
                    raise ValueError("datetime must be timezone-aware")
                values.append(value.astimezone(timezone.utc))
        if len(values) == 2 and (values[0] > values[1] or values[0].date() != values[1].date()):
            raise ValueError("Sportmonks requires an ordered single UTC day window")
        return (values[0] if values else datetime.now(timezone.utc)).date().isoformat()

    @staticmethod
    def _datetime(value: Any) -> datetime:
        try:
            if not isinstance(value, str):
                raise ValueError
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            # Sportmonks returns naive starting_at in the requested timezone (UTC).
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else (
                parsed.astimezone(timezone.utc)
            )
        except (ValueError, TypeError):
            raise ValueError("Sportmonks invalid fixture timestamp") from None

    @staticmethod
    def _id(value: Any) -> str:
        if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
            raise ValueError("Sportmonks required identifier missing")
        return str(value)

    def _normalize_fixture(self, item: Any) -> ProviderFixture:
        if not isinstance(item, dict):
            raise ValueError("Sportmonks fixture must be an object")
        external_id = self._id(item.get("id"))
        starts_at = self._datetime(item.get("starting_at"))
        state_id = item.get("state_id")
        if type(state_id) is not int:
            state_id = None
        status = self.STATUS_MAP.get(state_id, "unknown")
        teams = item.get("participants")
        if not isinstance(teams, list) or len(teams) != 2:
            raise ValueError("Sportmonks requires two participants")
        by_role = {}
        for team in teams:
            if not isinstance(team, dict) or not isinstance(team.get("meta"), dict):
                raise ValueError("Sportmonks participant metadata missing")
            role = team["meta"].get("location")
            if role not in ("home", "away") or role in by_role:
                raise ValueError("Sportmonks invalid participant locations")
            self._id(team.get("id"))
            if not isinstance(team.get("name"), str) or not team["name"].strip():
                raise ValueError("Sportmonks participant name missing")
            by_role[role] = team
        if self._id(by_role["home"]["id"]) == self._id(by_role["away"]["id"]):
            raise ValueError("Sportmonks duplicate participant")
        scores = self._scores(item.get("scores"), by_role)
        current = scores.get("CURRENT", {"home": None, "away": None})
        deciding = scores.get("PENALTIES", {}) if state_id == 8 else current
        participants = []
        for position, role in enumerate(("home", "away")):
            team = by_role[role]
            outcome = None
            if status == "finished":
                winner = team["meta"].get("winner")
                if winner is True:
                    outcome = "winner"
                elif any(t["meta"].get("winner") is True for t in by_role.values()):
                    outcome = "loser"
                elif all(type(deciding.get(r)) is int for r in ("home", "away")):
                    own, other = deciding[role], deciding["away" if role == "home" else "home"]
                    # An unresolved shootout or administrative result is not a draw.
                    if own != other:
                        outcome = "winner" if own > other else "loser"
                    elif state_id in (5, 7):
                        outcome = "draw"
            participants.append(ProviderParticipant(
                external_id=self._id(team["id"]), name=team["name"],
                short_name=team.get("short_code"), logo_url=team.get("image_path"),
                role=role, position=position, score={"value": current.get(role)},
                result_status=outcome,
            ))
        league = item.get("league") or {}
        season = item.get("season") or {}
        competition = None
        if isinstance(league, dict) and league.get("id") is not None and league.get("name"):
            country = league.get("country") or {}
            code = country.get("iso2") if isinstance(country, dict) else None
            competition = ProviderCompetition(
                external_id=self._id(league["id"]), name=str(league["name"]),
                jurisdiction_name=(
                    country["name"].strip() or None
                    if isinstance(country, dict) and isinstance(country.get("name"), str) else None
                ),
                country_code=(
                    code.upper()
                    if isinstance(code, str) and len(code) == 2
                    and code.isascii() and code.isalpha() else None
                ),
                season=str(season["name"]) if isinstance(season, dict) and season.get("name") else None,
                logo_url=league.get("image_path"),
            )
        periods = item.get("periods") or []
        minutes = [p["minutes"] for p in periods if isinstance(p, dict)
                   and type(p.get("minutes")) is int] if isinstance(periods, list) else []
        venue = item.get("venue") or {}
        return ProviderFixture(
            external_id=external_id, sport_slug="football", starts_at=starts_at, status=status,
            name=f"{participants[0].name} vs {participants[1].name}",
            participants=participants, competition=competition,
            live_clock=str(max(minutes)) if minutes else None,
            venue=venue.get("name") if isinstance(venue, dict) else None,
            result={"goals": current, "score": {
                "halftime": scores.get("1ST_HALF", {"home": None, "away": None}),
                "fulltime": scores.get("2ND_HALF", {"home": None, "away": None}),
                "extratime": current if state_id == 7 or (state_id == 8 and
                    any(k in scores for k in ("EXTRA_TIME", "EXTRA_TIME_ONLY")))
                    else {"home": None, "away": None},
                "penalty": scores.get("PENALTIES", {"home": None, "away": None}),
            }},
            metadata={"provider_state_id": state_id},
            source_updated_at=self._datetime(item["last_processed_at"])
            if item.get("last_processed_at") else None,
        )

    @staticmethod
    def _scores(raw: Any, teams: dict[str, Any]) -> dict[str, dict[str, int | None]]:
        if raw is None:
            return {}
        if not isinstance(raw, list):
            raise ValueError("Sportmonks scores must be a list")
        scores = {}
        roles = {str(team["id"]): role for role, team in teams.items()}
        for entry in raw:
            if not isinstance(entry, dict) or not isinstance(entry.get("score"), dict):
                raise ValueError("Sportmonks invalid score")
            description = entry.get("description")
            if description not in ("CURRENT", "1ST_HALF", "2ND_HALF", "PENALTIES",
                                   "EXTRA_TIME", "EXTRA_TIME_ONLY"):
                continue
            role = roles.get(str(entry.get("participant_id")))
            value = entry["score"].get("goals")
            if role is None or (value is not None and (type(value) is not int or value < 0)):
                raise ValueError("Sportmonks invalid score participant or value")
            scores.setdefault(description, {"home": None, "away": None})[role] = value
        return scores
