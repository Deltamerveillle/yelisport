"""Public SMS Discover athlete showcase composition service."""

import uuid

from app.core.exceptions import NotFoundError
from app.repositories.athlete_performance_repository import AthletePerformanceRepository
from app.repositories.discover_athlete_repository import DiscoverAthleteRepository
from app.repositories.discover_video_repository import DiscoverVideoRepository
from app.schemas.athlete_passport import AthletePassportResponse
from app.schemas.athlete_performance import AthletePerformanceResponse
from app.schemas.discover_athlete import (
    DiscoverAthleteIdentityResponse,
    DiscoverAthleteProfileResponse,
    DiscoverAthletePublicStatisticsEvidenceResponse,
    DiscoverAthletePublicStatisticsResponse,
)
from app.schemas.discover_video import DiscoverVideoResponse
from app.sms24.player_statistics_evidence import AthleteStatisticsEvidenceReader


class DiscoverAthleteProfileService:
    """Compose a public-safe showcase for an opted-in Discover athlete."""

    def __init__(
        self,
        *,
        discover_repository: DiscoverAthleteRepository,
        performance_repository: AthletePerformanceRepository,
        statistics_reader: AthleteStatisticsEvidenceReader,
        video_repository: DiscoverVideoRepository,
    ) -> None:
        self.discover_repository = discover_repository
        self.performance_repository = performance_repository
        self.statistics_reader = statistics_reader
        self.video_repository = video_repository

    async def get_profile(
        self,
        athlete_id: uuid.UUID,
    ) -> DiscoverAthleteProfileResponse:
        """Return the public showcase without mutating persisted data."""
        discoverable = (
            await self.discover_repository.get_discoverable_by_athlete_id(
                athlete_id
            )
        )
        if discoverable is None:
            raise NotFoundError("Discover athlete not found")

        athlete = discoverable.athlete

        performances = await self.performance_repository.list_by_athlete_id(
            athlete.id
        )
        evidence = await self.statistics_reader.read(athlete_id=athlete.id)
        videos = await self.video_repository.list_public_by_athlete_id(
            athlete.id
        )

        public_observations = [
            DiscoverAthletePublicStatisticsEvidenceResponse(
                scope=item.scope,
                period_label=item.period_label,
                metrics=item.metrics,
                fetched_at=item.fetched_at,
                source_updated_at=item.source_updated_at,
            )
            for item in evidence.observations
        ]

        return DiscoverAthleteProfileResponse(
            athlete=DiscoverAthleteIdentityResponse.model_validate(athlete),
            passport=(
                AthletePassportResponse.model_validate(discoverable.passport)
                if discoverable.passport is not None
                else None
            ),
            performances=[
                AthletePerformanceResponse.model_validate(performance)
                for performance in performances
            ],
            statistics=DiscoverAthletePublicStatisticsResponse(
                linked=evidence.linked,
                observations=public_observations,
            ),
            videos=[
                DiscoverVideoResponse.model_validate(video)
                for video in videos
            ],
        )
