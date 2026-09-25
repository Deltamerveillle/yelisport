"""Read-only enriched athlete profile projection service."""

import uuid

from app.core.exceptions import NotFoundError
from app.repositories.athlete_performance_repository import AthletePerformanceRepository
from app.repositories.athlete_repository import AthleteRepository
from app.schemas.athlete import AthleteResponse
from app.schemas.athlete_performance import AthletePerformanceResponse
from app.schemas.athlete_profile import (
    AthleteProfileResponse,
    AthleteStatisticsEvidenceResponse,
    AthleteStatisticsIdentityResponse,
    AthleteStatisticsResponse,
)
from app.sms24.player_statistics_evidence import AthleteStatisticsEvidenceReader


class AthleteProfileService:
    """Compose the human athlete profile with explicitly linked SMS24 evidence."""

    def __init__(
        self,
        *,
        athlete_repository: AthleteRepository,
        performance_repository: AthletePerformanceRepository,
        statistics_reader: AthleteStatisticsEvidenceReader,
    ) -> None:
        self.athlete_repository = athlete_repository
        self.performance_repository = performance_repository
        self.statistics_reader = statistics_reader

    async def get_profile(self, athlete_id: uuid.UUID) -> AthleteProfileResponse:
        """Return an enriched athlete profile without mutating persisted data."""
        athlete = await self.athlete_repository.get_by_id(athlete_id)
        if athlete is None:
            raise NotFoundError("Athlete not found")

        performances = await self.performance_repository.list_by_athlete_id(
            athlete.id
        )
        evidence = await self.statistics_reader.read(athlete_id=athlete.id)

        identity = AthleteStatisticsIdentityResponse(
            linked=evidence.linked,
            identity_link_id=evidence.identity_link_id,
            status=evidence.identity_status,
            method=evidence.identity_method,
            canonical_competitor_id=evidence.canonical_competitor_id,
        )

        observations = [
            AthleteStatisticsEvidenceResponse(
                observation_id=item.observation_id,
                source_id=item.source_id,
                sport_id=item.sport_id,
                provider_competitor_id=item.provider_competitor_id,
                athlete_external_id=item.athlete_external_id,
                scope=item.scope,
                period_label=item.period_label,
                metrics=item.metrics,
                metadata=item.metadata,
                fetched_at=item.fetched_at,
                source_updated_at=item.source_updated_at,
            )
            for item in evidence.observations
        ]

        return AthleteProfileResponse(
            athlete=AthleteResponse.model_validate(athlete),
            performances=[
                AthletePerformanceResponse.model_validate(performance)
                for performance in performances
            ],
            statistics=AthleteStatisticsResponse(
                identity=identity,
                observations=observations,
            ),
        )
