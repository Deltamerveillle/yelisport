"""Tests for SMS Talent business rules."""

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.talent_service import TalentService


def build_service() -> TalentService:
    service = TalentService(AsyncMock())
    service.athletes = AsyncMock()
    service.applications = AsyncMock()
    service.evaluations = AsyncMock()
    service.user_roles = AsyncMock()
    service.user_roles.get_by_user_and_role.return_value = SimpleNamespace(
        is_active=True,
        is_verified=True,
    )
    service.subscription_service = AsyncMock()
    return service


def application(
    *,
    status: str = "submitted",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status=status,
        completed_at=None,
    )


def evaluation(
    *,
    application_id: uuid.UUID,
    evaluator_user_id: uuid.UUID | None = None,
    status: str = "assigned",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        application_id=application_id,
        evaluator_user_id=evaluator_user_id or uuid.uuid4(),
        status=status,
        scores=None,
        overall_score=None,
        recommendation=None,
        comments=None,
        submitted_at=None,
    )


@pytest.mark.asyncio
async def test_athlete_cannot_evaluate_own_application() -> None:
    service = build_service()
    app = application()

    service.applications.get_by_id.return_value = app

    with pytest.raises(
        ValueError,
        match="Athlete cannot evaluate own application",
    ):
        await service.assign_evaluator(
            application_id=app.id,
            evaluator_user_id=app.user_id,
        )

    service.evaluations.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_evaluator_cannot_be_assigned_twice() -> None:
    service = build_service()
    app = application()
    evaluator_id = uuid.uuid4()

    service.applications.get_by_id.return_value = app
    service.evaluations.get_for_evaluator.return_value = evaluation(
        application_id=app.id,
        evaluator_user_id=evaluator_id,
    )

    with pytest.raises(
        ValueError,
        match="Evaluator already assigned",
    ):
        await service.assign_evaluator(
            application_id=app.id,
            evaluator_user_id=evaluator_id,
        )

    service.evaluations.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_fourth_evaluator_is_rejected() -> None:
    service = build_service()
    app = application()
    evaluator_id = uuid.uuid4()

    service.applications.get_by_id.return_value = app
    service.evaluations.get_for_evaluator.return_value = None
    service.evaluations.count_for_application.return_value = 3

    with pytest.raises(
        ValueError,
        match="already has three evaluators",
    ):
        await service.assign_evaluator(
            application_id=app.id,
            evaluator_user_id=evaluator_id,
        )

    service.evaluations.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_assigned_evaluator_can_be_added() -> None:
    service = build_service()
    app = application()
    evaluator_id = uuid.uuid4()

    service.applications.get_by_id.return_value = app
    service.evaluations.get_for_evaluator.return_value = None
    service.evaluations.count_for_application.return_value = 2

    created = evaluation(
        application_id=app.id,
        evaluator_user_id=evaluator_id,
    )
    service.evaluations.create.return_value = created

    result = await service.assign_evaluator(
        application_id=app.id,
        evaluator_user_id=evaluator_id,
    )

    assert result is created
    service.evaluations.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_submitted_evaluation_is_irreversibly_locked() -> None:
    service = build_service()
    app = application()
    evaluator_id = uuid.uuid4()

    locked = evaluation(
        application_id=app.id,
        evaluator_user_id=evaluator_id,
        status="submitted",
    )

    service.applications.get_by_id.return_value = app
    service.evaluations.get_for_evaluator.return_value = locked

    with pytest.raises(
        ValueError,
        match="Talent evaluation is locked",
    ):
        await service.submit_evaluation(
            application_id=app.id,
            evaluator_user_id=evaluator_id,
            scores={"technical": 80},
            overall_score=Decimal("80"),
        )

    service.evaluations.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_evaluator_only_gets_own_evaluation() -> None:
    service = build_service()
    app = application()
    evaluator_id = uuid.uuid4()

    own = evaluation(
        application_id=app.id,
        evaluator_user_id=evaluator_id,
    )
    service.evaluations.get_for_evaluator.return_value = own

    result = await service.get_evaluation_for_evaluator(
        application_id=app.id,
        evaluator_user_id=evaluator_id,
    )

    assert result is own

    service.evaluations.list_for_application.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_evaluations_hidden_before_completion() -> None:
    service = build_service()
    app = application(status="submitted")

    service.applications.get_by_id.return_value = app

    with pytest.raises(
        ValueError,
        match="remain confidential until completion",
    ):
        await service.get_completed_evaluations(
            application_id=app.id,
        )

    service.evaluations.list_for_application.assert_not_awaited()


@pytest.mark.asyncio
async def test_third_submitted_evaluation_completes_application() -> None:
    service = build_service()
    app = application()
    evaluator_id = uuid.uuid4()

    current = evaluation(
        application_id=app.id,
        evaluator_user_id=evaluator_id,
    )

    service.applications.get_by_id.return_value = app
    service.evaluations.get_for_evaluator.return_value = current
    service.evaluations.update.return_value = current
    service.evaluations.count_submitted_for_application.return_value = 3
    service.applications.update.return_value = app

    result = await service.submit_evaluation(
        application_id=app.id,
        evaluator_user_id=evaluator_id,
        scores={
            "technical": 82,
            "physical": 78,
        },
        overall_score=Decimal("80"),
        recommendation="recommended",
        comments="Strong potential",
    )

    assert result.status == "submitted"
    assert result.overall_score == Decimal("80")
    assert result.submitted_at is not None

    assert app.status == "completed"
    assert app.completed_at is not None

    service.applications.update.assert_awaited_once_with(app)


@pytest.mark.asyncio
async def test_completed_application_reveals_exactly_three_submitted_evaluations() -> None:
    service = build_service()
    app = application(status="completed")

    evaluations = [
        evaluation(
            application_id=app.id,
            status="submitted",
        )
        for _ in range(3)
    ]

    service.applications.get_by_id.return_value = app
    service.evaluations.list_for_application.return_value = evaluations

    result = await service.get_completed_evaluations(
        application_id=app.id,
    )

    assert result == evaluations
    assert len(result) == 3


@pytest.mark.asyncio
async def test_create_application_requires_existing_athlete() -> None:
    service = build_service()
    service.athletes.get_by_id.return_value = None

    with pytest.raises(
        ValueError,
        match="Athlete not found",
    ):
        await service.create_application(
            athlete_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )

    service.applications.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_cannot_apply_for_another_athlete() -> None:
    service = build_service()

    athlete = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        sport_id=uuid.uuid4(),
    )

    service.athletes.get_by_id.return_value = athlete

    with pytest.raises(
        ValueError,
        match="another athlete",
    ):
        await service.create_application(
            athlete_id=athlete.id,
            user_id=uuid.uuid4(),
        )

    service.subscription_service.has_premium_access.assert_not_awaited()
    service.applications.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_application_requires_premium_access() -> None:
    service = build_service()

    user_id = uuid.uuid4()
    athlete = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        sport_id=uuid.uuid4(),
    )

    service.athletes.get_by_id.return_value = athlete
    service.subscription_service.has_premium_access.return_value = False

    with pytest.raises(
        ValueError,
        match="Active premium access is required",
    ):
        await service.create_application(
            athlete_id=athlete.id,
            user_id=user_id,
        )

    service.applications.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_premium_owner_can_create_talent_application() -> None:
    service = build_service()

    user_id = uuid.uuid4()
    athlete = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        sport_id=uuid.uuid4(),
    )

    service.athletes.get_by_id.return_value = athlete
    service.subscription_service.has_premium_access.return_value = True
    service.applications.get_open_for_athlete.return_value = None

    async def fake_create(application):
        application.id = uuid.uuid4()
        return application

    service.applications.create.side_effect = fake_create

    result = await service.create_application(
        athlete_id=athlete.id,
        user_id=user_id,
    )

    assert result.athlete_id == athlete.id
    assert result.user_id == user_id
    assert result.sport_id == athlete.sport_id
    assert result.status == "draft"

    service.subscription_service.has_premium_access.assert_awaited_once_with(
        user_id
    )
    service.applications.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_owner_can_add_submission_item_to_draft_application() -> None:
    service = build_service()
    service.submission_items = AsyncMock()

    user_id = uuid.uuid4()
    app = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        status="draft",
    )

    service.applications.get_by_id.return_value = app

    async def fake_create(item):
        item.id = uuid.uuid4()
        return item

    service.submission_items.create.side_effect = fake_create

    result = await service.add_submission_item(
        application_id=app.id,
        user_id=user_id,
        item_type="video",
        resource_url="https://example.com/video.mp4",
        title="Technical test",
        description="Private evaluation video",
        metadata_json={"position": "midfielder"},
    )

    assert result.application_id == app.id
    assert result.item_type == "video"
    assert result.resource_url == "https://example.com/video.mp4"


@pytest.mark.asyncio
async def test_submission_item_rejected_after_application_submission() -> None:
    service = build_service()
    service.submission_items = AsyncMock()

    user_id = uuid.uuid4()
    app = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        status="submitted",
    )

    service.applications.get_by_id.return_value = app

    with pytest.raises(
        ValueError,
        match="materials are locked after submission",
    ):
        await service.add_submission_item(
            application_id=app.id,
            user_id=user_id,
            item_type="video",
            resource_url="https://example.com/video.mp4",
        )


@pytest.mark.asyncio
async def test_other_user_cannot_access_submission_items() -> None:
    service = build_service()
    service.submission_items = AsyncMock()

    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()

    app = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=owner_id,
        status="draft",
    )

    service.applications.get_by_id.return_value = app

    with pytest.raises(
        ValueError,
        match="cannot access another Talent application",
    ):
        await service.list_submission_items(
            application_id=app.id,
            user_id=other_user_id,
        )


@pytest.mark.asyncio
async def test_submit_application_requires_submission_item() -> None:
    service = build_service()
    service.submission_items = AsyncMock()

    user_id = uuid.uuid4()
    app = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        status="draft",
        submitted_at=None,
    )

    service.applications.get_by_id.return_value = app
    service.submission_items.list_by_application_id.return_value = []

    with pytest.raises(
        ValueError,
        match="requires at least one submission item",
    ):
        await service.submit_application(
            application_id=app.id,
            user_id=user_id,
        )


@pytest.mark.asyncio
async def test_submit_application_locks_materials_and_sets_timestamp() -> None:
    service = build_service()
    service.submission_items = AsyncMock()

    user_id = uuid.uuid4()
    app = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        status="draft",
        submitted_at=None,
    )

    service.applications.get_by_id.return_value = app
    service.submission_items.list_by_application_id.return_value = [
        SimpleNamespace(id=uuid.uuid4())
    ]
    service.applications.update.return_value = app

    result = await service.submit_application(
        application_id=app.id,
        user_id=user_id,
    )

    assert result.status == "submitted"
    assert result.submitted_at is not None

    service.applications.get_by_id.assert_awaited_with(
        app.id,
        for_update=True,
    )


@pytest.mark.asyncio
async def test_owner_can_delete_submission_item_while_draft() -> None:
    service = build_service()
    service.submission_items = AsyncMock()

    user_id = uuid.uuid4()
    app = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        status="draft",
    )
    item = SimpleNamespace(
        id=uuid.uuid4(),
        application_id=app.id,
    )

    service.applications.get_by_id.return_value = app
    service.submission_items.get_by_id.return_value = item

    await service.delete_submission_item(
        application_id=app.id,
        item_id=item.id,
        user_id=user_id,
    )

    service.submission_items.delete.assert_awaited_once_with(item)


@pytest.mark.asyncio
async def test_create_application_rejects_existing_open_application() -> None:
    service = TalentService(AsyncMock())

    user_id = uuid.uuid4()
    athlete_id = uuid.uuid4()
    sport_id = uuid.uuid4()

    athlete = SimpleNamespace(
        id=athlete_id,
        user_id=user_id,
        sport_id=sport_id,
    )

    existing = SimpleNamespace(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        user_id=user_id,
        sport_id=sport_id,
        status="submitted",
    )

    service.athletes = AsyncMock()
    service.applications = AsyncMock()
    service.subscription_service = AsyncMock()

    service.athletes.get_by_id.return_value = athlete
    service.subscription_service.has_premium_access.return_value = True
    service.applications.get_open_for_athlete.return_value = existing

    with pytest.raises(
        ValueError,
        match="Athlete already has an open SMS Talent application",
    ):
        await service.create_application(
            user_id=user_id,
            athlete_id=athlete_id,
        )

    service.applications.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_draft_application_cannot_receive_evaluator() -> None:
    service = build_service()

    application_id = uuid.uuid4()
    evaluator_user_id = uuid.uuid4()

    draft_application = application(status="draft")
    draft_application.id = application_id

    service.applications.get_by_id.return_value = draft_application

    with pytest.raises(
        ValueError,
        match=(
            "Talent application must be submitted "
            "before evaluator assignment"
        ),
    ):
        await service.assign_evaluator(
            application_id=application_id,
            evaluator_user_id=evaluator_user_id,
        )

    service.evaluations.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_evaluator_without_sms_role_cannot_be_assigned() -> None:
    service = build_service()

    application_id = uuid.uuid4()
    evaluator_user_id = uuid.uuid4()

    submitted_application = application(status="submitted")
    submitted_application.id = application_id

    service.applications.get_by_id.return_value = (
        submitted_application
    )
    service.user_roles.get_by_user_and_role.return_value = None

    with pytest.raises(
        ValueError,
        match="Evaluator must be an active and verified SMS evaluator",
    ):
        await service.assign_evaluator(
            application_id=application_id,
            evaluator_user_id=evaluator_user_id,
        )

    service.evaluations.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_inactive_sms_evaluator_cannot_be_assigned() -> None:
    service = build_service()

    application_id = uuid.uuid4()
    evaluator_user_id = uuid.uuid4()

    submitted_application = application(status="submitted")
    submitted_application.id = application_id

    service.applications.get_by_id.return_value = (
        submitted_application
    )
    service.user_roles.get_by_user_and_role.return_value = (
        SimpleNamespace(
            is_active=False,
            is_verified=True,
        )
    )

    with pytest.raises(
        ValueError,
        match="Evaluator must be an active and verified SMS evaluator",
    ):
        await service.assign_evaluator(
            application_id=application_id,
            evaluator_user_id=evaluator_user_id,
        )

    service.evaluations.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_unverified_sms_evaluator_cannot_be_assigned() -> None:
    service = build_service()

    application_id = uuid.uuid4()
    evaluator_user_id = uuid.uuid4()

    submitted_application = application(status="submitted")
    submitted_application.id = application_id

    service.applications.get_by_id.return_value = (
        submitted_application
    )
    service.user_roles.get_by_user_and_role.return_value = (
        SimpleNamespace(
            is_active=True,
            is_verified=False,
        )
    )

    with pytest.raises(
        ValueError,
        match="Evaluator must be an active and verified SMS evaluator",
    ):
        await service.assign_evaluator(
            application_id=application_id,
            evaluator_user_id=evaluator_user_id,
        )

    service.evaluations.create.assert_not_awaited()
