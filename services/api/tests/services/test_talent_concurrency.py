"""Real PostgreSQL concurrency tests for SMS Talent."""

import asyncio
import uuid

import pytest
from sqlalchemy import delete, func, select

from app.db.session import SessionFactory
from app.models.athlete import Athlete
from app.models.sport import Sport
from app.models.talent_application import TalentApplication
from app.models.talent_evaluation import TalentEvaluation
from app.models.user import User
from app.models.user_role import UserRole
from app.services.talent_service import TalentService


@pytest.mark.asyncio(loop_scope="module")
async def test_concurrent_assignment_never_creates_four_evaluators() -> None:
    owner_id = uuid.uuid4()
    evaluator_ids = [uuid.uuid4() for _ in range(4)]
    sport_id = uuid.uuid4()
    athlete_id = uuid.uuid4()
    application_id = uuid.uuid4()

    all_user_ids = [owner_id, *evaluator_ids]

    # ---------------------------------------------------------
    # Arrange: real PostgreSQL rows
    # ---------------------------------------------------------
    async with SessionFactory() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    email=f"sms-talent-{user_id}@example.test",
                    is_active=True,
                )
                for user_id in all_user_ids
            ]
        )

        session.add(
            Sport(
                id=sport_id,
                slug=f"talent-concurrency-{sport_id}",
                name="SMS Talent Concurrency Test",
                is_active=True,
            )
        )

        # Users and sport must exist before Athlete foreign keys are inserted.
        await session.flush()

        # Every evaluator must be an active, verified SMS evaluator.
        session.add_all(
            [
                UserRole(
                    user_id=evaluator_user_id,
                    role="sms_evaluator",
                    is_active=True,
                    is_verified=True,
                )
                for evaluator_user_id in evaluator_ids
            ]
        )

        await session.flush()

        session.add(
            Athlete(
                id=athlete_id,
                user_id=owner_id,
                sport_id=sport_id,
                first_name="SMS",
                last_name="Talent",
            )
        )

        # Athlete must exist before TalentApplication references it.
        await session.flush()

        session.add(
            TalentApplication(
                id=application_id,
                athlete_id=athlete_id,
                user_id=owner_id,
                sport_id=sport_id,
                status="submitted",
            )
        )

        # Application must exist before evaluations reference it.
        await session.flush()

        # Two evaluator slots are already occupied.
        session.add_all(
            [
                TalentEvaluation(
                    application_id=application_id,
                    evaluator_user_id=evaluator_ids[0],
                    status="assigned",
                ),
                TalentEvaluation(
                    application_id=application_id,
                    evaluator_user_id=evaluator_ids[1],
                    status="assigned",
                ),
            ]
        )

        await session.commit()

    start = asyncio.Event()

    async def attempt_assignment(
        evaluator_user_id: uuid.UUID,
    ) -> str:
        async with SessionFactory() as session:
            service = TalentService(session)

            # Both transactions wait here before competing.
            await start.wait()

            try:
                await service.assign_evaluator(
                    application_id=application_id,
                    evaluator_user_id=evaluator_user_id,
                )
                await session.commit()
                return "assigned"

            except ValueError as exc:
                await session.rollback()

                if "already has three evaluators" not in str(exc):
                    raise

                return "rejected"

            except Exception:
                await session.rollback()
                raise

    try:
        # -----------------------------------------------------
        # Act: two real DB transactions compete for slot #3
        # -----------------------------------------------------
        task_3 = asyncio.create_task(
            attempt_assignment(evaluator_ids[2])
        )
        task_4 = asyncio.create_task(
            attempt_assignment(evaluator_ids[3])
        )

        await asyncio.sleep(0)
        start.set()

        results = await asyncio.gather(task_3, task_4)

        # -----------------------------------------------------
        # Assert
        # -----------------------------------------------------
        assert sorted(results) == ["assigned", "rejected"]

        async with SessionFactory() as session:
            count_result = await session.execute(
                select(func.count(TalentEvaluation.id)).where(
                    TalentEvaluation.application_id == application_id
                )
            )
            evaluator_count = int(count_result.scalar_one())

            ids_result = await session.execute(
                select(TalentEvaluation.evaluator_user_id).where(
                    TalentEvaluation.application_id == application_id
                )
            )
            assigned_ids = set(ids_result.scalars().all())

        assert evaluator_count == 3

        assert evaluator_ids[0] in assigned_ids
        assert evaluator_ids[1] in assigned_ids

        # Exactly one of the two concurrent contenders won.
        concurrent_winners = assigned_ids.intersection(
            {evaluator_ids[2], evaluator_ids[3]}
        )
        assert len(concurrent_winners) == 1

    finally:
        # -----------------------------------------------------
        # Cleanup: leave the development DB unchanged
        # -----------------------------------------------------
        async with SessionFactory() as session:
            await session.execute(
                delete(TalentEvaluation).where(
                    TalentEvaluation.application_id == application_id
                )
            )

            await session.execute(
                delete(TalentApplication).where(
                    TalentApplication.id == application_id
                )
            )

            await session.execute(
                delete(Athlete).where(
                    Athlete.id == athlete_id
                )
            )

            await session.execute(
                delete(User).where(
                    User.id.in_(all_user_ids)
                )
            )

            await session.execute(
                delete(Sport).where(
                    Sport.id == sport_id
                )
            )

            await session.commit()


@pytest.mark.asyncio(loop_scope="module")
async def test_concurrent_final_evaluations_complete_application() -> None:
    """
    Two final evaluators may submit concurrently.

    The Talent application row lock must serialize completion so that
    the application cannot remain stuck in "submitted" after all three
    independent evaluations have been submitted.
    """
    from datetime import datetime, timezone
    from decimal import Decimal

    owner_id = uuid.uuid4()
    evaluator_ids = [
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    ]
    all_user_ids = [owner_id, *evaluator_ids]

    sport_id = uuid.uuid4()
    athlete_id = uuid.uuid4()
    application_id = uuid.uuid4()

    evaluation_ids = [
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    ]

    # ---------------------------------------------------------
    # Arrange: real PostgreSQL records
    # ---------------------------------------------------------
    async with SessionFactory() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    email=f"{user_id}@sms-talent.test",
                )
                for user_id in all_user_ids
            ]
        )

        session.add(
            Sport(
                id=sport_id,
                slug=f"talent-concurrency-{sport_id}",
                name="Talent Concurrency Test",
            )
        )

        await session.flush()

        session.add(
            Athlete(
                id=athlete_id,
                user_id=owner_id,
                sport_id=sport_id,
                first_name="SMS",
                last_name="Concurrency",
            )
        )

        await session.flush()

        session.add(
            TalentApplication(
                id=application_id,
                athlete_id=athlete_id,
                user_id=owner_id,
                sport_id=sport_id,
                status="submitted",
                submitted_at=datetime.now(timezone.utc),
            )
        )

        await session.flush()

        # Evaluator #1 has already submitted.
        # Evaluators #2 and #3 will submit concurrently.
        session.add_all(
            [
                TalentEvaluation(
                    id=evaluation_ids[0],
                    application_id=application_id,
                    evaluator_user_id=evaluator_ids[0],
                    status="submitted",
                    scores={"technical": 70},
                    overall_score=Decimal("70"),
                    recommendation="recommended",
                    submitted_at=datetime.now(timezone.utc),
                ),
                TalentEvaluation(
                    id=evaluation_ids[1],
                    application_id=application_id,
                    evaluator_user_id=evaluator_ids[1],
                    status="assigned",
                ),
                TalentEvaluation(
                    id=evaluation_ids[2],
                    application_id=application_id,
                    evaluator_user_id=evaluator_ids[2],
                    status="assigned",
                ),
            ]
        )

        await session.commit()

    start = asyncio.Event()

    async def submit_final_evaluation(
        evaluator_user_id: uuid.UUID,
        score: Decimal,
    ) -> str:
        async with SessionFactory() as session:
            service = TalentService(session)

            await start.wait()

            try:
                result = await service.submit_evaluation(
                    application_id=application_id,
                    evaluator_user_id=evaluator_user_id,
                    scores={
                        "technical": int(score),
                        "physical": int(score),
                    },
                    overall_score=score,
                    recommendation="recommended",
                    comments="Concurrent evaluation test",
                )

                await session.commit()
                return result.status

            except Exception:
                await session.rollback()
                raise

    try:
        # -----------------------------------------------------
        # Act: final two evaluators submit at the same time
        # -----------------------------------------------------
        task_2 = asyncio.create_task(
            submit_final_evaluation(
                evaluator_ids[1],
                Decimal("81"),
            )
        )

        task_3 = asyncio.create_task(
            submit_final_evaluation(
                evaluator_ids[2],
                Decimal("84"),
            )
        )

        await asyncio.sleep(0)
        start.set()

        results = await asyncio.gather(task_2, task_3)

        # -----------------------------------------------------
        # Assert
        # -----------------------------------------------------
        assert results == ["submitted", "submitted"]

        async with SessionFactory() as session:
            application = await session.get(
                TalentApplication,
                application_id,
            )

            evaluation_result = await session.execute(
                select(TalentEvaluation).where(
                    TalentEvaluation.application_id == application_id
                )
            )
            evaluations = list(
                evaluation_result.scalars().all()
            )

        assert application is not None
        assert application.status == "completed"
        assert application.completed_at is not None

        assert len(evaluations) == 3
        assert all(
            evaluation.status == "submitted"
            for evaluation in evaluations
        )

    finally:
        # -----------------------------------------------------
        # Cleanup: leave development DB unchanged
        # -----------------------------------------------------
        async with SessionFactory() as session:
            await session.execute(
                delete(TalentEvaluation).where(
                    TalentEvaluation.application_id == application_id
                )
            )

            await session.execute(
                delete(TalentApplication).where(
                    TalentApplication.id == application_id
                )
            )

            await session.execute(
                delete(Athlete).where(
                    Athlete.id == athlete_id
                )
            )

            await session.execute(
                delete(User).where(
                    User.id.in_(all_user_ids)
                )
            )

            await session.execute(
                delete(Sport).where(
                    Sport.id == sport_id
                )
            )

            await session.commit()


@pytest.mark.asyncio(loop_scope="module")
async def test_concurrent_application_creation_allows_only_one_open() -> None:
    """
    Two concurrent creation attempts for the same athlete must never
    create two open SMS Talent applications.

    The athlete row lock serializes the business check, while the
    PostgreSQL partial unique index remains the final database guard.
    """
    owner_id = uuid.uuid4()
    sport_id = uuid.uuid4()
    athlete_id = uuid.uuid4()

    # ---------------------------------------------------------
    # Arrange: real PostgreSQL records
    # ---------------------------------------------------------
    async with SessionFactory() as session:
        session.add(
            User(
                id=owner_id,
                email=f"sms-talent-create-{owner_id}@example.test",
                is_active=True,
            )
        )

        session.add(
            Sport(
                id=sport_id,
                slug=f"talent-create-concurrency-{sport_id}",
                name="SMS Talent Create Concurrency Test",
                is_active=True,
            )
        )

        await session.flush()

        session.add(
            Athlete(
                id=athlete_id,
                user_id=owner_id,
                sport_id=sport_id,
                first_name="SMS",
                last_name="ConcurrentCreate",
            )
        )

        await session.commit()

    start = asyncio.Event()

    class PremiumAccessStub:
        async def has_premium_access(self, *args, **kwargs) -> bool:
            return True

    async def attempt_creation() -> str:
        async with SessionFactory() as session:
            service = TalentService(session)

            # Payment/access itself is not under test here.
            service.subscription_service = PremiumAccessStub()

            await start.wait()

            try:
                await service.create_application(
                    user_id=owner_id,
                    athlete_id=athlete_id,
                )
                await session.commit()
                return "created"

            except ValueError as exc:
                await session.rollback()

                if (
                    "Athlete already has an open SMS Talent application"
                    not in str(exc)
                ):
                    raise

                return "rejected"

            except Exception:
                await session.rollback()
                raise

    try:
        # -----------------------------------------------------
        # Act: two transactions compete for the same athlete
        # -----------------------------------------------------
        task_1 = asyncio.create_task(attempt_creation())
        task_2 = asyncio.create_task(attempt_creation())

        await asyncio.sleep(0)
        start.set()

        results = await asyncio.gather(task_1, task_2)

        # -----------------------------------------------------
        # Assert: exactly one succeeds
        # -----------------------------------------------------
        assert sorted(results) == ["created", "rejected"]

        async with SessionFactory() as session:
            count_result = await session.execute(
                select(func.count(TalentApplication.id)).where(
                    TalentApplication.athlete_id == athlete_id,
                    TalentApplication.status.in_(
                        ("draft", "submitted")
                    ),
                )
            )

            open_application_count = int(
                count_result.scalar_one()
            )

        assert open_application_count == 1

    finally:
        # -----------------------------------------------------
        # Cleanup: leave development DB unchanged
        # -----------------------------------------------------
        async with SessionFactory() as session:
            await session.execute(
                delete(TalentApplication).where(
                    TalentApplication.athlete_id == athlete_id
                )
            )

            await session.execute(
                delete(Athlete).where(
                    Athlete.id == athlete_id
                )
            )

            await session.execute(
                delete(User).where(
                    User.id == owner_id
                )
            )

            await session.execute(
                delete(Sport).where(
                    Sport.id == sport_id
                )
            )

            await session.commit()
