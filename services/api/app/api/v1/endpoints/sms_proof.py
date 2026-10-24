"""SMS Proof performance verification API."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db_session
from app.schemas.sms_proof import (
    SMSProofDecisionRequest,
    SMSProofVerificationResponse,
)
from app.services.sms_proof_service import SMSProofService

router = APIRouter(tags=["SMS Proof"])


@router.post(
    "/sms-proof/performances/{performance_id}/verify",
    response_model=SMSProofVerificationResponse,
    status_code=201,
)
async def verify_athlete_performance(
    performance_id: uuid.UUID,
    data: SMSProofDecisionRequest,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Record an authorized, auditable performance decision."""

    service = SMSProofService(session)

    try:
        verification = await service.verify_performance(
            performance_id=performance_id,
            verifier_user_id=uuid.UUID(str(current_user.id)),
            decision=data.decision,
            reason=data.reason,
            evidence=data.evidence,
        )

        await session.commit()
        await session.refresh(verification)
        return verification

    except Exception:
        await session.rollback()
        raise


@router.get(
    "/sms-proof/performances/{performance_id}/verifications",
    response_model=list[SMSProofVerificationResponse],
)
async def list_performance_verifications(
    performance_id: uuid.UUID,
    current_user: CurrentUser,
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
):
    """Return verification history to authorized SMS administrators."""

    service = SMSProofService(session)

    return await service.list_verifications(
        performance_id=performance_id,
        requester_user_id=uuid.UUID(str(current_user.id)),
    )
