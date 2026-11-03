"""SMS Talent qualification against isolated disposable PostgreSQL."""

import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.models.athlete import Athlete
from app.models.country import Country
from app.models.sport import Sport
from app.models.talent_application import TalentApplication
from app.models.talent_evaluation import TalentEvaluation
from app.models.user import User
from app.services.talent_service import TalentService

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("scores", "expected"),
    [
        (["75", "68", "82"], "eligible_for_coaching"),
        (["75", "68", "50"], "improvement_and_reevaluation"),
        (["75", "68", "50.01"], "eligible_for_coaching"),
        (["90", "40", "95"], "improvement_and_reevaluation"),
    ],
)
async def test_three_persisted_human_evaluations(scores, expected):
    url = os.environ.get("SMS24_MIGRATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Disposable PostgreSQL test database required")

    engine = create_async_engine(url, poolclass=NullPool)
    schema = f"sms_talent_test_{uuid.uuid4().hex}"

    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                await connection.execute(
                    text(f'CREATE SCHEMA "{schema}"')
                )
                await connection.execute(
                    text(f'SET LOCAL search_path TO "{schema}"')
                )

                await connection.run_sync(
                    lambda sync: Base.metadata.create_all(
                        sync,
                        tables=[
                            model.__table__
                            for model in (
                                Sport,
                                Country,
                                User,
                                Athlete,
                                TalentApplication,
                                TalentEvaluation,
                            )
                        ],
                    )
                )

                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    owner = User(
                        id=uuid.uuid4(),
                        email=f"{uuid.uuid4()}@example.test",
                    )
                    evaluators = [
                        User(
                            id=uuid.uuid4(),
                            email=f"{uuid.uuid4()}@example.test",
                        )
                        for _ in range(3)
                    ]
                    sport = Sport(slug="football", name="Football")
                    session.add_all([owner, *evaluators, sport])
                    await session.flush()

                    athlete = Athlete(
                        user_id=owner.id,
                        sport_id=sport.id,
                        first_name="Test",
                        last_name="Talent",
                    )
                    session.add(athlete)
                    await session.flush()

                    application = TalentApplication(
                        athlete_id=athlete.id,
                        user_id=owner.id,
                        sport_id=sport.id,
                        status="completed",
                    )
                    session.add(application)
                    await session.flush()

                    for evaluator, score in zip(evaluators, scores):
                        session.add(
                            TalentEvaluation(
                                application_id=application.id,
                                evaluator_user_id=evaluator.id,
                                status="submitted",
                                overall_score=Decimal(score),
                            )
                        )
                    await session.flush()
                    application_id = application.id
                    session.expire_all()

                    actual = await TalentService(
                        session
                    ).get_qualification_status(
                        application_id=application_id
                    )
                    assert actual == expected
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
