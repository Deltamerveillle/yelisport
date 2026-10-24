"""Local rail preparation only; caller owns the transaction and provider selection."""

from typing import cast

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.yeleni_pay_rail_transaction import YeleniPayRailTransaction
from app.repositories.payment_transaction_repository import PaymentTransactionRepository
from app.schemas.payment_rail import RailCode, RailInitializationRequest, RailInitializationResult


class YeleniPayRailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.payments = PaymentTransactionRepository(session)

    async def prepare(
        self, *, payment_reference: str, rail_code: str
    ) -> tuple[YeleniPayRailTransaction, RailInitializationRequest]:
        rail_code = TypeAdapter(RailCode).validate_python(rail_code, strict=True)
        # Existing repository locks user -> payment. Rail lock always follows.
        payment = await self.payments.get_by_reference(payment_reference)
        if payment is None:
            raise NotFoundError("Payment not found")
        if payment.provider != "yeleni-pay" or payment.status != "pending":
            raise ConflictError("Payment is not eligible for rail initialization")
        rail = cast(YeleniPayRailTransaction | None, await self.session.scalar(
            select(YeleniPayRailTransaction)
            .where(
                YeleniPayRailTransaction.payment_transaction_id == payment.id,
            )
            .with_for_update()
        ))
        if rail is not None and rail.rail_code != rail_code:
            raise ConflictError("Payment already assigned to another rail")
        if rail is not None and rail.status not in {"created", "pending"}:
            raise ConflictError("Rail transaction is terminal")
        if rail is None:
            rail = YeleniPayRailTransaction(payment_transaction_id=payment.id, rail_code=rail_code)
            self.session.add(rail)
            await self.session.flush()
            await self.session.refresh(rail)
        request = RailInitializationRequest(
            idempotency_key=rail.id,
            payment_reference=payment.reference,
            amount_minor=payment.amount_minor,
            currency=payment.currency,
        )
        return rail, request

    async def record_initialization(
        self,
        *,
        payment_reference: str,
        rail_code: str,
        result: RailInitializationResult,
    ) -> YeleniPayRailTransaction:
        if not isinstance(result, RailInitializationResult):
            raise ValueError("Invalid rail initialization result")
        result = RailInitializationResult.model_validate(result.model_dump())
        rail, _ = await self.prepare(payment_reference=payment_reference, rail_code=rail_code)
        if rail.external_transaction_id is not None:
            if rail.external_transaction_id != result.external_transaction_id:
                raise ConflictError("Rail identity cannot be replaced")
            return rail
        rail.external_transaction_id = result.external_transaction_id
        rail.status = "pending"
        await self.session.flush()
        await self.session.refresh(rail)
        return rail
