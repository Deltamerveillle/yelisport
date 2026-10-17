"""Local Transfers foundation. No HTTP, implicit human creation, or name matching.

Callers own transactions and authorize identity-review decisions. Provider snapshots
only update observations. Canonical events and human links require explicit UUIDs;
provider data does not grant verification or mutate Athlete/Passport/eligibility.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.sports_live import (
    SportsCanonicalCompetition,
    SportsCanonicalCompetitor,
    SportsCompetitor,
    SportsSeason,
)
from app.models.sports_transfers import (
    SportsAthleteIdentityLink,
    SportsCanonicalTransfer,
    SportsTransferObservation,
)
from app.sms24.providers.transfers import (
    ProviderTransfer,
    _timestamp,
    build_transfer_observation_key,
)


class SMS24TransfersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _locked(self, model, identity):
        row = await self.session.scalar(
            select(model)
            .where(model.id == identity)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise ValueError("Unknown explicit transfer graph identity")
        return row

    async def _competitor(self, identity, *, kind, sport_id=None):
        row = await self._locked(SportsCanonicalCompetitor, identity)
        if row.competitor_type != kind or (sport_id is not None and row.sport_id != sport_id):
            raise ValueError("Transfer competitor has an incompatible type or sport")
        return row

    async def link_athlete(
        self,
        *,
        athlete_id: uuid.UUID,
        canonical_competitor_id: uuid.UUID,
        method: str,
        established_by: str,
        evidence_reference: str,
        status: str = "declared",
        verified_at: datetime | None = None,
    ) -> SportsAthleteIdentityLink:
        """Record an explicit authorized decision, never a provider/name inference.

        One active link on each side. End a previous decision explicitly before
        replacing it. Verification requires an institutional review and timestamp.
        """
        _timestamp(verified_at)
        async with self.session.begin_nested():
            athlete = await self._locked(Athlete, athlete_id)
            await self._competitor(
                canonical_competitor_id, kind="athlete", sport_id=athlete.sport_id
            )
            link = SportsAthleteIdentityLink(
                athlete_id=athlete_id,
                canonical_competitor_id=canonical_competitor_id,
                method=method,
                established_by=established_by,
                evidence_reference=evidence_reference,
                status=status,
                verified_at=verified_at,
            )
            self.session.add(link)
            await self.session.flush()
            return link

    async def create_event(
        self,
        *,
        canonical_athlete_id: uuid.UUID,
        from_club_id: uuid.UUID | None = None,
        to_club_id: uuid.UUID | None = None,
        season_id: uuid.UUID | None = None,
        movement_date: date | None = None,
        movement_type: str = "unknown",
        status: str = "unknown",
        display_type: str | None = None,
        fee_amount: Decimal | None = None,
        fee_currency: str | None = None,
    ) -> SportsCanonicalTransfer:
        """Create an explicit event; no deduplication by athlete, clubs, or date.

        A season is an explicitly mapped competition-scoped SportsSeason. Calendar
        years and provider season labels are never guessed into this foreign key.
        """
        if movement_date is not None and type(movement_date) is not date:
            raise ValueError("Movement date must be a date, or unknown")
        async with self.session.begin_nested():
            athlete = await self._competitor(canonical_athlete_id, kind="athlete")
            for club_id in (from_club_id, to_club_id):
                if club_id is not None:
                    await self._competitor(club_id, kind="team", sport_id=athlete.sport_id)
            if season_id is not None:
                season = await self._locked(SportsSeason, season_id)
                competition = await self._locked(
                    SportsCanonicalCompetition, season.canonical_competition_id
                )
                if competition.sport_id != athlete.sport_id:
                    raise ValueError("Transfer season has an incompatible sport")
            event = SportsCanonicalTransfer(
                canonical_athlete_id=canonical_athlete_id,
                from_club_id=from_club_id,
                to_club_id=to_club_id,
                season_id=season_id,
                movement_date=movement_date,
                movement_type=movement_type,
                status=status,
                display_type=display_type,
                fee_amount=fee_amount,
                fee_currency=fee_currency,
            )
            self.session.add(event)
            await self.session.flush()
            return event

    async def record_observation(
        self,
        *,
        source_id: uuid.UUID,
        transfer: ProviderTransfer,
        fetched_at: datetime,
    ) -> SportsTransferObservation:
        """Upsert a source record only; stale snapshots cannot overwrite newer data.

        The source's event identity cannot silently change athlete. Graph resolution
        is never overwritten here, and unknown provider fields stay NULL. A mutable
        latest snapshot follows existing SMS24 observation conventions (not a log).
        """
        _timestamp(fetched_at, required=True)
        key = build_transfer_observation_key(transfer)
        values = {
            name: getattr(transfer, name)
            for name in (
                "external_id",
                "record_reference",
                "athlete_external_id",
                "athlete_name",
                "from_team_external_id",
                "from_team_name",
                "to_team_external_id",
                "to_team_name",
                "reported_date",
                "reported_type",
                "source_updated_at",
            )
        }
        values.update(metadata_json=transfer.metadata, fetched_at=fetched_at)
        async with self.session.begin_nested():
            stmt = (
                insert(SportsTransferObservation)
                .values(
                    source_id=source_id,
                    observation_key=key,
                    **values,
                )
                .on_conflict_do_update(
                    constraint="uq_sports_transfers_observation",
                    set_={**values, "updated_at": func.now()},
                    where=(SportsTransferObservation.fetched_at <= fetched_at)
                    & (
                        SportsTransferObservation.athlete_external_id
                        == transfer.athlete_external_id
                    ),
                )
                .returning(SportsTransferObservation)
                .execution_options(populate_existing=True)
            )
            observation = (await self.session.execute(stmt)).scalar_one_or_none()
            if observation is None:
                observation = await self.session.scalar(
                    select(SportsTransferObservation)
                    .where(
                        SportsTransferObservation.source_id == source_id,
                        SportsTransferObservation.observation_key == key,
                    )
                    .execution_options(populate_existing=True)
                )
                if observation.athlete_external_id != transfer.athlete_external_id:
                    raise ValueError(
                        "A provider transfer identity cannot change athlete implicitly"
                    )
            return observation

    async def resolve_observation(
        self,
        *,
        observation_id: uuid.UUID,
        athlete_competitor_id: uuid.UUID,
        canonical_transfer_id: uuid.UUID | None = None,
    ) -> SportsTransferObservation:
        """Explicit mapping only; require exact source/player identity and graph coherence.

        Existing mappings cannot be silently replaced. Reconciliation is deliberately
        outside this foundation. No comparison of player/team names establishes a link.
        """
        async with self.session.begin_nested():
            observation = await self._locked(SportsTransferObservation, observation_id)
            competitor = await self._locked(SportsCompetitor, athlete_competitor_id)
            if (
                competitor.competitor_type != "athlete"
                or competitor.source_id != observation.source_id
                or competitor.external_id != observation.athlete_external_id
            ):
                raise ValueError("Provider athlete observation must match source, ID, and type")
            if observation.athlete_competitor_id not in (None, athlete_competitor_id):
                raise ValueError(
                    "Existing provider athlete mapping requires explicit reconciliation"
                )
            if observation.canonical_transfer_id not in (None, canonical_transfer_id):
                raise ValueError("Existing transfer mapping requires explicit reconciliation")
            if canonical_transfer_id is not None:
                event = await self._locked(SportsCanonicalTransfer, canonical_transfer_id)
                await self._competitor(
                    event.canonical_athlete_id, kind="athlete", sport_id=competitor.sport_id
                )
                if competitor.canonical_competitor_id != event.canonical_athlete_id:
                    raise ValueError(
                        "Provider athlete must explicitly resolve to the event athlete"
                    )
            observation.athlete_competitor_id = athlete_competitor_id
            observation.canonical_transfer_id = canonical_transfer_id
            await self.session.flush()
            return observation
