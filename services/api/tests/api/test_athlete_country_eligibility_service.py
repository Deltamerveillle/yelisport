import asyncio
import uuid
from types import SimpleNamespace

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.schemas.athlete_country_eligibility import (
    AthleteCountryEligibilityCreate,
)
from app.services.athlete_country_eligibility_service import (
    AthleteCountryEligibilityService,
)


USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
ATHLETE_ID = uuid.uuid4()
COUNTRY_ID = uuid.uuid4()


class FakeAthleteRepository:
    def __init__(self, athlete=None):
        self.athlete = athlete
        self.for_update = None

    async def get_by_id(self, athlete_id, *, for_update=False):
        assert athlete_id == ATHLETE_ID
        self.for_update = for_update
        return self.athlete


class FakeCountryRepository:
    def __init__(self, country=None):
        self.country = country

    async def get_by_id(self, country_id):
        assert country_id == COUNTRY_ID
        return self.country


class FakeEligibilityRepository:
    def __init__(self, existing=None):
        self.existing = existing
        self.primary_cleared = False
        self.created = None
        self.items = []

    async def get_by_athlete_and_country(
        self,
        *,
        athlete_id,
        country_id,
    ):
        assert athlete_id == ATHLETE_ID
        assert country_id == COUNTRY_ID
        return self.existing

    async def clear_primary_for_athlete(self, athlete_id):
        assert athlete_id == ATHLETE_ID
        self.primary_cleared = True

    async def create(
        self,
        *,
        athlete_id,
        country_id,
        is_primary=False,
    ):
        self.created = SimpleNamespace(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            country_id=country_id,
            status="declared",
            is_primary=is_primary,
        )
        return self.created

    async def list_by_athlete(self, athlete_id):
        assert athlete_id == ATHLETE_ID
        return self.items


def owned_athlete():
    return SimpleNamespace(
        id=ATHLETE_ID,
        user_id=USER_ID,
    )


def active_country():
    return SimpleNamespace(
        id=COUNTRY_ID,
        is_active=True,
    )


def test_owner_can_declare_country_eligibility():
    athlete_repository = FakeAthleteRepository(owned_athlete())
    eligibility_repository = FakeEligibilityRepository()

    service = AthleteCountryEligibilityService(
        eligibility_repository,
        athlete_repository,
        FakeCountryRepository(active_country()),
    )

    result = asyncio.run(
        service.declare_eligibility(
            athlete_id=ATHLETE_ID,
            data=AthleteCountryEligibilityCreate(
                country_id=COUNTRY_ID,
                is_primary=False,
            ),
            current_user_id=USER_ID,
        )
    )

    assert result.athlete_id == ATHLETE_ID
    assert result.country_id == COUNTRY_ID
    assert result.status == "declared"
    assert result.is_primary is True
    assert eligibility_repository.primary_cleared is False
    assert athlete_repository.for_update is True


def test_non_owner_cannot_declare_country_eligibility():
    athlete = SimpleNamespace(
        id=ATHLETE_ID,
        user_id=OTHER_USER_ID,
    )

    service = AthleteCountryEligibilityService(
        FakeEligibilityRepository(),
        FakeAthleteRepository(athlete),
        FakeCountryRepository(active_country()),
    )

    with pytest.raises(
        ForbiddenError,
        match="permission to manage this athlete eligibility",
    ):
        asyncio.run(
            service.declare_eligibility(
                athlete_id=ATHLETE_ID,
                data=AthleteCountryEligibilityCreate(
                    country_id=COUNTRY_ID,
                ),
                current_user_id=USER_ID,
            )
        )


def test_unknown_athlete_cannot_declare_eligibility():
    service = AthleteCountryEligibilityService(
        FakeEligibilityRepository(),
        FakeAthleteRepository(None),
        FakeCountryRepository(active_country()),
    )

    with pytest.raises(
        NotFoundError,
        match="Athlete not found",
    ):
        asyncio.run(
            service.declare_eligibility(
                athlete_id=ATHLETE_ID,
                data=AthleteCountryEligibilityCreate(
                    country_id=COUNTRY_ID,
                ),
                current_user_id=USER_ID,
            )
        )


def test_inactive_country_is_rejected():
    service = AthleteCountryEligibilityService(
        FakeEligibilityRepository(),
        FakeAthleteRepository(owned_athlete()),
        FakeCountryRepository(
            SimpleNamespace(
                id=COUNTRY_ID,
                is_active=False,
            )
        ),
    )

    with pytest.raises(
        NotFoundError,
        match="Country not found or inactive",
    ):
        asyncio.run(
            service.declare_eligibility(
                athlete_id=ATHLETE_ID,
                data=AthleteCountryEligibilityCreate(
                    country_id=COUNTRY_ID,
                ),
                current_user_id=USER_ID,
            )
        )


def test_duplicate_country_eligibility_is_rejected():
    existing = SimpleNamespace(
        athlete_id=ATHLETE_ID,
        country_id=COUNTRY_ID,
    )

    service = AthleteCountryEligibilityService(
        FakeEligibilityRepository(existing=existing),
        FakeAthleteRepository(owned_athlete()),
        FakeCountryRepository(active_country()),
    )

    with pytest.raises(
        ConflictError,
        match="already declared",
    ):
        asyncio.run(
            service.declare_eligibility(
                athlete_id=ATHLETE_ID,
                data=AthleteCountryEligibilityCreate(
                    country_id=COUNTRY_ID,
                ),
                current_user_id=USER_ID,
            )
        )


def test_new_primary_country_clears_previous_primary():
    eligibility_repository = FakeEligibilityRepository()
    eligibility_repository.items = [
        SimpleNamespace(
            id=uuid.uuid4(),
            athlete_id=ATHLETE_ID,
            country_id=uuid.uuid4(),
            status="declared",
            is_primary=True,
        )
    ]

    service = AthleteCountryEligibilityService(
        eligibility_repository,
        FakeAthleteRepository(owned_athlete()),
        FakeCountryRepository(active_country()),
    )

    result = asyncio.run(
        service.declare_eligibility(
            athlete_id=ATHLETE_ID,
            data=AthleteCountryEligibilityCreate(
                country_id=COUNTRY_ID,
                is_primary=True,
            ),
            current_user_id=USER_ID,
        )
    )

    assert eligibility_repository.primary_cleared is True
    assert result.is_primary is True


def test_non_primary_country_does_not_clear_existing_primary():
    eligibility_repository = FakeEligibilityRepository()
    eligibility_repository.items = [
        SimpleNamespace(
            id=uuid.uuid4(),
            athlete_id=ATHLETE_ID,
            country_id=uuid.uuid4(),
            status="declared",
            is_primary=True,
        )
    ]

    service = AthleteCountryEligibilityService(
        eligibility_repository,
        FakeAthleteRepository(owned_athlete()),
        FakeCountryRepository(active_country()),
    )

    result = asyncio.run(
        service.declare_eligibility(
            athlete_id=ATHLETE_ID,
            data=AthleteCountryEligibilityCreate(
                country_id=COUNTRY_ID,
                is_primary=False,
            ),
            current_user_id=USER_ID,
        )
    )

    assert eligibility_repository.primary_cleared is False
    assert result.is_primary is False
