"""Read-only Player Statistics evidence for explicitly linked SMS athletes.

Provider observations remain SMS24 evidence. They are never promoted to
AthletePerformance and this module never creates or infers human identity.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sports_live import SportsCanonicalCompetitor, SportsCompetitor
from app.models.sports_player_statistics import SportsPlayerStatisticObservation
from app.models.sports_transfers import SportsAthleteIdentityLink


@dataclass(frozen=True, slots=True)
class AthleteStatisticsEvidence:
    observation_id: uuid.UUID
    source_id: uuid.UUID
    sport_id: uuid.UUID
    provider_competitor_id: uuid.UUID
    athlete_external_id: str
    scope: str
    period_label: str | None
    metrics: dict
    metadata: dict
    fetched_at: datetime
    source_updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class AthleteStatisticsEvidenceResult:
    athlete_id: uuid.UUID
    identity_link_id: uuid.UUID | None
    identity_status: str | None
    identity_method: str | None
    canonical_competitor_id: uuid.UUID | None
    observations: tuple[AthleteStatisticsEvidence, ...] = ()

    @property
    def linked(self) -> bool:
        return self.identity_link_id is not None


class AthleteStatisticsEvidenceReader:
    """Resolve statistics only through an active explicit athlete identity link."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def read(
        self,
        *,
        athlete_id: uuid.UUID,
    ) -> AthleteStatisticsEvidenceResult:
        try:
            athlete_id = uuid.UUID(str(athlete_id))
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("athlete_id must be a UUID") from exc

        link = await self.session.scalar(
            select(SportsAthleteIdentityLink).where(
                SportsAthleteIdentityLink.athlete_id == athlete_id,
                SportsAthleteIdentityLink.ended_at.is_(None),
            )
        )

        if link is None:
            return AthleteStatisticsEvidenceResult(
                athlete_id=athlete_id,
                identity_link_id=None,
                identity_status=None,
                identity_method=None,
                canonical_competitor_id=None,
            )

        canonical = await self.session.scalar(
            select(SportsCanonicalCompetitor).where(
                SportsCanonicalCompetitor.id == link.canonical_competitor_id,
            )
        )
        if canonical is None:
            raise ValueError("Active athlete identity link has no canonical competitor")
        if canonical.competitor_type != "athlete":
            raise ValueError("Active athlete identity link must reference an athlete competitor")

        rows = (
            await self.session.execute(
                select(
                    SportsPlayerStatisticObservation,
                    SportsCompetitor.id,
                )
                .join(
                    SportsCompetitor,
                    SportsCompetitor.id
                    == SportsPlayerStatisticObservation.athlete_competitor_id,
                )
                .where(
                    SportsCompetitor.canonical_competitor_id == canonical.id,
                    SportsCompetitor.competitor_type == "athlete",
                    SportsCompetitor.sport_id == canonical.sport_id,
                    SportsPlayerStatisticObservation.sport_id == canonical.sport_id,
                    SportsPlayerStatisticObservation.source_id == SportsCompetitor.source_id,
                    SportsPlayerStatisticObservation.athlete_external_id
                    == SportsCompetitor.external_id,
                )
                .order_by(
                    SportsPlayerStatisticObservation.fetched_at.desc(),
                    SportsPlayerStatisticObservation.id,
                )
            )
        ).all()

        observations = tuple(
            AthleteStatisticsEvidence(
                observation_id=observation.id,
                source_id=observation.source_id,
                sport_id=observation.sport_id,
                provider_competitor_id=provider_competitor_id,
                athlete_external_id=observation.athlete_external_id,
                scope=observation.scope,
                period_label=observation.period_label,
                metrics=dict(observation.metrics_json),
                metadata=dict(observation.metadata_json),
                fetched_at=observation.fetched_at,
                source_updated_at=observation.source_updated_at,
            )
            for observation, provider_competitor_id in rows
        )

        return AthleteStatisticsEvidenceResult(
            athlete_id=athlete_id,
            identity_link_id=link.id,
            identity_status=link.status,
            identity_method=link.method,
            canonical_competitor_id=canonical.id,
            observations=observations,
        )
