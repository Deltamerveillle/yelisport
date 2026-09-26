"""Public catalogue and authenticated local payment intentions."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.payment import CommercialPlan, PaymentInitiationRequest, PaymentResponse
from app.services.payment_initiation_service import PaymentInitiationService

router = APIRouter(prefix="/payments", tags=["payments"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Configuration = Annotated[Settings, Depends(get_settings)]


@router.get("/plans", response_model=list[CommercialPlan])
async def list_plans(settings: Configuration):
    return [p for p in settings.sms_commercial_plans if p.active and p.purchasable]


@router.post("/initiate", response_model=PaymentResponse)
async def initiate_payment(
    data: PaymentInitiationRequest,
    current_user: CurrentUser,
    session: Session,
    settings: Configuration,
):
    try:
        transaction = await PaymentInitiationService(
            session, settings.sms_commercial_plans
        ).initiate(user_id=uuid.UUID(str(current_user.id)), plan_code=data.plan_code)
        response = PaymentResponse.model_validate(transaction)
        await session.commit()
        return response
    except Exception:
        await session.rollback()
        raise


@router.get("/{transaction_id}", response_model=PaymentResponse)
async def get_payment(
    transaction_id: uuid.UUID,
    current_user: CurrentUser,
    session: Session,
    settings: Configuration,
):
    transaction = await PaymentInitiationService(session, settings.sms_commercial_plans).get_owned(
        user_id=uuid.UUID(str(current_user.id)), transaction_id=transaction_id
    )
    return PaymentResponse.model_validate(transaction)
