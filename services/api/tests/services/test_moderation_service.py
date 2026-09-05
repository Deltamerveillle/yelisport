"""Service tests for SMS moderation."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.schemas.moderation import (
    UserModerationAction,
    DiscoverModerationDecision,
    ModerationReportCreate,
    ModerationTransitionRequest,
)
from app.services.moderation_service import ModerationService


REPORTER_ID = uuid.uuid4()
ADMIN_ID = uuid.uuid4()
TARGET_USER_ID = uuid.uuid4()
RESOURCE_ID = uuid.uuid4()
REPORT_ID = uuid.uuid4()


def build_service():
    session = SimpleNamespace()

    service = ModerationService(session)

    service.reports = SimpleNamespace(
        create=AsyncMock(),
        get_by_id=AsyncMock(),
        get_by_id_for_update=AsyncMock(),
        list_for_reporter=AsyncMock(),
        list_for_admin=AsyncMock(),
        save=AsyncMock(),
    )

    service.events = SimpleNamespace(
        create=AsyncMock(),
        list_for_report=AsyncMock(),
    )

    service.roles = SimpleNamespace(
        get_verified_admin_role=AsyncMock(),
    )

    service._validate_resource = AsyncMock()

    return service


def make_create_data(
    *,
    resource_type="discover_video",
    resource_id=RESOURCE_ID,
    reason="inappropriate_content",
    details="Contenu à vérifier.",
):
    return ModerationReportCreate(
        resource_type=resource_type,
        resource_id=resource_id,
        reason=reason,
        details=details,
    )


def make_report(
    *,
    status="submitted",
    reporter_user_id=REPORTER_ID,
):
    return SimpleNamespace(
        id=REPORT_ID,
        reporter_user_id=reporter_user_id,
        resource_type="discover_video",
        resource_id=RESOURCE_ID,
        reason="inappropriate_content",
        details="Contenu à vérifier.",
        status=status,
    )


@pytest.mark.asyncio
async def test_create_report_creates_report_and_audit_event():
    service = build_service()

    created = make_report()

    service.reports.create.return_value = created

    result = await service.create_report(
        reporter_user_id=REPORTER_ID,
        data=make_create_data(),
    )

    assert result == created

    service._validate_resource.assert_awaited_once_with(
        resource_type="discover_video",
        resource_id=RESOURCE_ID,
    )

    service.reports.create.assert_awaited_once()

    created_report = (
        service.reports.create.await_args.args[0]
    )

    assert created_report.reporter_user_id == REPORTER_ID
    assert created_report.resource_type == "discover_video"
    assert created_report.resource_id == RESOURCE_ID
    assert created_report.status == "submitted"

    service.events.create.assert_awaited_once()

    event = service.events.create.await_args.args[0]

    assert event.report_id == REPORT_ID
    assert event.actor_user_id == REPORTER_ID
    assert event.actor_role == "user"
    assert event.action == "submitted"
    assert event.from_status is None
    assert event.to_status == "submitted"


@pytest.mark.asyncio
async def test_create_report_rejects_self_user_report():
    service = build_service()

    data = make_create_data(
        resource_type="user",
        resource_id=REPORTER_ID,
    )

    with pytest.raises(ForbiddenError):
        await service.create_report(
            reporter_user_id=REPORTER_ID,
            data=data,
        )

    service.reports.create.assert_not_awaited()
    service.events.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_report_propagates_missing_resource():
    service = build_service()

    service._validate_resource.side_effect = (
        NotFoundError(
            "Moderation resource not found"
        )
    )

    with pytest.raises(NotFoundError):
        await service.create_report(
            reporter_user_id=REPORTER_ID,
            data=make_create_data(),
        )

    service.reports.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_my_reports_is_scoped_to_reporter():
    service = build_service()

    expected = [make_report()]

    service.reports.list_for_reporter.return_value = (
        expected
    )

    result = await service.list_my_reports(
        reporter_user_id=REPORTER_ID,
        limit=25,
        offset=5,
    )

    assert result == expected

    (
        service.reports
        .list_for_reporter
        .assert_awaited_once_with(
            reporter_user_id=REPORTER_ID,
            limit=25,
            offset=5,
        )
    )


@pytest.mark.asyncio
async def test_admin_queue_requires_verified_admin():
    service = build_service()

    service.roles.get_verified_admin_role.return_value = None

    with pytest.raises(ForbiddenError):
        await service.list_admin_reports(
            admin_user_id=ADMIN_ID,
        )

    service.reports.list_for_admin.assert_not_awaited()


@pytest.mark.asyncio
async def test_verified_admin_can_filter_queue():
    service = build_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    expected = [make_report()]

    service.reports.list_for_admin.return_value = (
        expected
    )

    result = await service.list_admin_reports(
        admin_user_id=ADMIN_ID,
        status="submitted",
        resource_type="discover_video",
        limit=20,
        offset=2,
    )

    assert result == expected

    service.reports.list_for_admin.assert_awaited_once_with(
        status="submitted",
        resource_type="discover_video",
        limit=20,
        offset=2,
    )


@pytest.mark.asyncio
async def test_admin_can_move_submitted_to_under_review():
    service = build_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    report = make_report(
        status="submitted"
    )

    service.reports.get_by_id_for_update.return_value = (
        report
    )
    service.reports.save.return_value = report

    result = await service.transition_report(
        report_id=REPORT_ID,
        admin_user_id=ADMIN_ID,
        data=ModerationTransitionRequest(
            status="under_review",
            note="Analyse commencée.",
        ),
    )

    assert result == report
    assert report.status == "under_review"

    service.events.create.assert_awaited_once()

    event = service.events.create.await_args.args[0]

    assert event.report_id == REPORT_ID
    assert event.actor_user_id == ADMIN_ID
    assert event.actor_role == "admin"
    assert event.action == "under_review"
    assert event.from_status == "submitted"
    assert event.to_status == "under_review"
    assert event.note == "Analyse commencée."


@pytest.mark.asyncio
async def test_admin_can_resolve_report_under_review():
    service = build_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    report = make_report(
        status="under_review"
    )

    service.reports.get_by_id_for_update.return_value = (
        report
    )
    service.reports.save.return_value = report

    result = await service.transition_report(
        report_id=REPORT_ID,
        admin_user_id=ADMIN_ID,
        data=ModerationTransitionRequest(
            status="resolved",
            note="Vérification terminée.",
        ),
    )

    assert result.status == "resolved"


@pytest.mark.asyncio
async def test_invalid_transition_is_rejected():
    service = build_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    report = make_report(
        status="submitted"
    )

    service.reports.get_by_id_for_update.return_value = (
        report
    )

    with pytest.raises(ConflictError):
        await service.transition_report(
            report_id=REPORT_ID,
            admin_user_id=ADMIN_ID,
            data=ModerationTransitionRequest(
                status="resolved",
            ),
        )

    service.reports.save.assert_not_awaited()
    service.events.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_transition_missing_report_returns_not_found():
    service = build_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    service.reports.get_by_id_for_update.return_value = None

    with pytest.raises(NotFoundError):
        await service.transition_report(
            report_id=REPORT_ID,
            admin_user_id=ADMIN_ID,
            data=ModerationTransitionRequest(
                status="under_review",
            ),
        )


@pytest.mark.asyncio
async def test_admin_can_read_report_audit_history():
    service = build_service()

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    service.reports.get_by_id.return_value = make_report()

    expected = [
        SimpleNamespace(
            id=uuid.uuid4(),
            action="submitted",
        )
    ]

    service.events.list_for_report.return_value = expected

    result = await service.list_report_events(
        report_id=REPORT_ID,
        admin_user_id=ADMIN_ID,
    )

    assert result == expected

    service.events.list_for_report.assert_awaited_once_with(
        REPORT_ID
    )



@pytest.mark.asyncio
async def test_admin_approves_discover_video_under_review():
    service = build_service()

    service.videos = SimpleNamespace(
        get_by_id=AsyncMock(),
        update=AsyncMock(),
    )

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    report = make_report(
        status="under_review"
    )

    video = SimpleNamespace(
        id=RESOURCE_ID,
        publication_status="published",
        moderation_status="pending",
        is_active=True,
    )

    service.reports.get_by_id_for_update.return_value = (
        report
    )
    service.reports.save.return_value = report
    service.videos.get_by_id.return_value = video
    service.videos.update.return_value = video

    result = await service.decide_discover_video(
        report_id=REPORT_ID,
        admin_user_id=ADMIN_ID,
        data=DiscoverModerationDecision(
            decision="approved",
            note="Contenu validé.",
        ),
    )

    assert result is video
    assert video.moderation_status == "approved"
    assert report.status == "resolved"

    event = service.events.create.await_args.args[0]

    assert event.action == "discover_approved"
    assert event.from_status == "under_review"
    assert event.to_status == "resolved"
    assert event.actor_user_id == ADMIN_ID
    assert event.actor_role == "admin"
    assert event.note == "Contenu validé."


@pytest.mark.asyncio
async def test_admin_rejects_discover_video_under_review():
    service = build_service()

    service.videos = SimpleNamespace(
        get_by_id=AsyncMock(),
        update=AsyncMock(),
    )

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    report = make_report(
        status="under_review"
    )

    video = SimpleNamespace(
        id=RESOURCE_ID,
        publication_status="published",
        moderation_status="pending",
        is_active=True,
    )

    service.reports.get_by_id_for_update.return_value = report
    service.reports.save.return_value = report
    service.videos.get_by_id.return_value = video
    service.videos.update.return_value = video

    result = await service.decide_discover_video(
        report_id=REPORT_ID,
        admin_user_id=ADMIN_ID,
        data=DiscoverModerationDecision(
            decision="rejected",
            note="Contenu non conforme.",
        ),
    )

    assert result.moderation_status == "rejected"
    assert report.status == "resolved"

    event = service.events.create.await_args.args[0]

    assert event.action == "discover_rejected"


@pytest.mark.asyncio
async def test_discover_decision_requires_under_review_report():
    service = build_service()

    service.videos = SimpleNamespace(
        get_by_id=AsyncMock(),
        update=AsyncMock(),
    )

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    service.reports.get_by_id_for_update.return_value = (
        make_report(
            status="submitted"
        )
    )

    with pytest.raises(ConflictError):
        await service.decide_discover_video(
            report_id=REPORT_ID,
            admin_user_id=ADMIN_ID,
            data=DiscoverModerationDecision(
                decision="approved",
            ),
        )

    service.videos.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_discover_decision_rejects_wrong_resource_type():
    service = build_service()

    service.videos = SimpleNamespace(
        get_by_id=AsyncMock(),
        update=AsyncMock(),
    )

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    report = make_report(
        status="under_review"
    )
    report.resource_type = "user"

    service.reports.get_by_id_for_update.return_value = (
        report
    )

    with pytest.raises(ConflictError):
        await service.decide_discover_video(
            report_id=REPORT_ID,
            admin_user_id=ADMIN_ID,
            data=DiscoverModerationDecision(
                decision="approved",
            ),
        )

    service.videos.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_discover_decision_requires_published_video():
    service = build_service()

    service.videos = SimpleNamespace(
        get_by_id=AsyncMock(),
        update=AsyncMock(),
    )

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    report = make_report(
        status="under_review"
    )

    video = SimpleNamespace(
        id=RESOURCE_ID,
        publication_status="draft",
        moderation_status="pending",
        is_active=True,
    )

    service.reports.get_by_id_for_update.return_value = (
        report
    )
    service.videos.get_by_id.return_value = video

    with pytest.raises(ConflictError):
        await service.decide_discover_video(
            report_id=REPORT_ID,
            admin_user_id=ADMIN_ID,
            data=DiscoverModerationDecision(
                decision="approved",
            ),
        )

    service.videos.update.assert_not_awaited()



@pytest.mark.asyncio
async def test_admin_can_suspend_user_under_review():
    service = build_service()

    service.users = SimpleNamespace(
        get_by_id_for_update=AsyncMock(),
        save=AsyncMock(),
    )

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    report = make_report(
        status="under_review"
    )
    report.resource_type = "user"
    report.resource_id = TARGET_USER_ID

    user = SimpleNamespace(
        id=TARGET_USER_ID,
        is_active=True,
    )

    service.reports.get_by_id_for_update.return_value = report
    service.reports.save.return_value = report
    service.users.get_by_id_for_update.return_value = user
    service.users.save.return_value = user

    result = await service.moderate_user(
        report_id=REPORT_ID,
        admin_user_id=ADMIN_ID,
        data=UserModerationAction(
            action="suspend",
            note="Fraude confirmée.",
        ),
    )

    assert result.is_active is False
    assert report.status == "resolved"

    event = service.events.create.await_args.args[0]

    assert event.action == "user_suspended"
    assert event.actor_user_id == ADMIN_ID
    assert event.from_status == "under_review"
    assert event.to_status == "resolved"


@pytest.mark.asyncio
async def test_admin_can_reactivate_user_under_review():
    service = build_service()

    service.users = SimpleNamespace(
        get_by_id_for_update=AsyncMock(),
        save=AsyncMock(),
    )

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    report = make_report(
        status="under_review"
    )
    report.resource_type = "user"
    report.resource_id = TARGET_USER_ID

    user = SimpleNamespace(
        id=TARGET_USER_ID,
        is_active=False,
    )

    service.reports.get_by_id_for_update.return_value = report
    service.reports.save.return_value = report
    service.users.get_by_id_for_update.return_value = user
    service.users.save.return_value = user

    result = await service.moderate_user(
        report_id=REPORT_ID,
        admin_user_id=ADMIN_ID,
        data=UserModerationAction(
            action="reactivate",
        ),
    )

    assert result.is_active is True

    event = service.events.create.await_args.args[0]

    assert event.action == "user_reactivated"


@pytest.mark.asyncio
async def test_admin_cannot_moderate_self():
    service = build_service()

    service.users = SimpleNamespace(
        get_by_id_for_update=AsyncMock(),
        save=AsyncMock(),
    )

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    report = make_report(
        status="under_review"
    )
    report.resource_type = "user"
    report.resource_id = ADMIN_ID

    service.reports.get_by_id_for_update.return_value = report

    with pytest.raises(ForbiddenError):
        await service.moderate_user(
            report_id=REPORT_ID,
            admin_user_id=ADMIN_ID,
            data=UserModerationAction(
                action="suspend",
            ),
        )

    service.users.get_by_id_for_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_action_requires_under_review_report():
    service = build_service()

    service.users = SimpleNamespace(
        get_by_id_for_update=AsyncMock(),
        save=AsyncMock(),
    )

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    report = make_report(
        status="submitted"
    )
    report.resource_type = "user"
    report.resource_id = TARGET_USER_ID

    service.reports.get_by_id_for_update.return_value = report

    with pytest.raises(ConflictError):
        await service.moderate_user(
            report_id=REPORT_ID,
            admin_user_id=ADMIN_ID,
            data=UserModerationAction(
                action="suspend",
            ),
        )


@pytest.mark.asyncio
async def test_cannot_suspend_already_suspended_user():
    service = build_service()

    service.users = SimpleNamespace(
        get_by_id_for_update=AsyncMock(),
        save=AsyncMock(),
    )

    service.roles.get_verified_admin_role.return_value = (
        SimpleNamespace(
            role="admin"
        )
    )

    report = make_report(
        status="under_review"
    )
    report.resource_type = "user"
    report.resource_id = TARGET_USER_ID

    user = SimpleNamespace(
        id=TARGET_USER_ID,
        is_active=False,
    )

    service.reports.get_by_id_for_update.return_value = report
    service.users.get_by_id_for_update.return_value = user

    with pytest.raises(ConflictError):
        await service.moderate_user(
            report_id=REPORT_ID,
            admin_user_id=ADMIN_ID,
            data=UserModerationAction(
                action="suspend",
            ),
        )

    service.users.save.assert_not_awaited()
