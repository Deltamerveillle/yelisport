"""Experimental ESPN soccer adapter for SMS24.

Not registered by default. Evaluate data licensing before production use.
"""

from __future__ import annotations

from datetime import UTC, datetime
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


class ESPNProvider(SportsDataProvider):
    """Normalize ESPN English Premier League fixtures for local evaluation."""

    slug = "espn"
    name = "ESPN (experimental)"
    DEFAULT_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"

    def __init__(
        self,
        *,
        url: str | None = None,
        timeout_seconds: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.url = url or self.DEFAULT_URL
        self.timeout_seconds = timeout_seconds
        self._client = client

    async def _get_payload(self) -> dict[str, Any]:
        if self._client is not None:
            response = await self._client.get(self.url, timeout=self.timeout_seconds)
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.url, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
            raise ValueError("Invalid ESPN scoreboard payload")
        return payload

    @staticmethod
    def _aware(value: datetime | None) -> None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Date filters must include a timezone")

    @staticmethod
    def _logo(item: dict[str, Any]) -> str | None:
        logos = item.get("logos") or []
        if isinstance(logos, list) and logos and isinstance(logos[0], dict):
            return logos[0].get("href")
        return None

    @staticmethod
    def _status(item: dict[str, Any]) -> str:
        details = (item.get("status") or {}).get("type") or {}
        name = str(details.get("name") or "").upper()
        if "POSTPON" in name:
            return "postponed"
        if "CANCEL" in name or "ABANDON" in name:
            return "cancelled"
        if "SUSPEND" in name or "INTERRUPT" in name:
            return "suspended"
        return {"pre": "scheduled", "in": "live", "post": "finished"}.get(
            details.get("state"), "scheduled"
        )

    @classmethod
    def normalize_event(
        cls, event: dict[str, Any], league: dict[str, Any] | None = None
    ) -> ProviderFixture:
        event_id = event.get("id")
        if event_id is None:
            raise ValueError("ESPN event id is required")
        date_value = event.get("date")
        if not isinstance(date_value, str):
            raise ValueError("ESPN event date is required")
        starts_at = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        cls._aware(starts_at)
        competitions = event.get("competitions") or []
        if not competitions or not isinstance(competitions[0], dict):
            raise ValueError("ESPN event competition details are required")
        detail = competitions[0]
        status = cls._status(event)
        participants: list[ProviderParticipant] = []
        for item in detail.get("competitors") or []:
            team = item.get("team") or {}
            if team.get("id") is None or not team.get("displayName"):
                raise ValueError("ESPN team id and name are required")
            role = item.get("homeAway")
            if role not in ("home", "away"):
                raise ValueError("ESPN home/away role is required")
            score = item.get("score")
            if status == "scheduled" or score in (None, ""):
                score = None
            else:
                try:
                    score = int(score)
                except (TypeError, ValueError):
                    score = None
            participants.append(
                ProviderParticipant(
                    external_id=str(team["id"]),
                    name=str(team["displayName"]),
                    competitor_type="team",
                    short_name=team.get("shortDisplayName"),
                    logo_url=cls._logo(team),
                    position=0 if role == "home" else 1,
                    role=role,
                    score={"value": score},
                )
            )
        if len(participants) != 2 or {p.role for p in participants} != {"home", "away"}:
            raise ValueError("ESPN fixture must have home and away teams")
        participants.sort(key=lambda p: p.position)
        league = league or {}
        competition = None
        if league.get("id") is not None and league.get("name"):
            season = league.get("season") or {}
            season_name = season.get("displayName") if isinstance(season, dict) else None
            competition = ProviderCompetition(
                external_id=str(league["id"]),
                name=str(league["name"]),
                season=str(season_name or season.get("year")) if isinstance(season, dict) and (season_name or season.get("year")) else None,
                logo_url=cls._logo(league),
            )
        venue = detail.get("venue") or {}
        venue_name = venue.get("fullName") if isinstance(venue, dict) else None
        state = (event.get("status") or {}).get("type") or {}
        clock = (event.get("status") or {}).get("displayClock") if status == "live" else None
        goals = {p.role: p.score.get("value") for p in participants}
        return ProviderFixture(
            external_id=str(event_id),
            sport_slug="football",
            starts_at=starts_at,
            status=status,
            name=f"{participants[0].name} vs {participants[1].name}",
            live_clock=clock,
            venue=venue_name,
            competition=competition,
            participants=participants,
            result={"goals": goals},
            metadata={"provider_status": state.get("name"), "league_slug": league.get("slug")},
        )

    async def fetch_fixtures(
        self,
        *,
        sport_slug: str | None = None,
        starts_from: datetime | None = None,
        starts_until: datetime | None = None,
        live_only: bool = False,
    ) -> ProviderFetchResult:
        now = datetime.now(UTC)
        if sport_slug not in (None, "football"):
            return ProviderFetchResult(fetched_at=now)
        self._aware(starts_from)
        self._aware(starts_until)
        if starts_from is not None and starts_until is not None and starts_from > starts_until:
            raise ValueError("starts_from must be <= starts_until")
        payload = await self._get_payload()
        leagues = payload.get("leagues") or []
        league = leagues[0] if leagues and isinstance(leagues[0], dict) else None
        fixtures = []
        for event in payload["events"]:
            fixture = self.normalize_event(event, league)
            if starts_from is not None and fixture.starts_at < starts_from:
                continue
            if starts_until is not None and fixture.starts_at > starts_until:
                continue
            if live_only and fixture.status != "live":
                continue
            fixtures.append(fixture)
        return ProviderFetchResult(
            fixtures=fixtures,
            fetched_at=datetime.now(UTC),
            raw_count=len(payload["events"]),
        )

    async def check_health(self) -> ProviderHealthResult:
        checked_at = datetime.now(UTC)
        try:
            await self._get_payload()
        except (httpx.HTTPError, ValueError) as exc:
            return ProviderHealthResult(
                is_healthy=False, checked_at=checked_at, message=str(exc)
            )
        return ProviderHealthResult(is_healthy=True, checked_at=checked_at)
