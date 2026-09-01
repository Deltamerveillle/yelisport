"""SMS payment transaction model."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentTransaction(Base):
    """Provider-neutral payment transaction for SMS."""

    __tablename__ = "payment_transactions"

    __table_args__ = (
        UniqueConstraint(
            "reference",
            name="uq_payment_transactions_reference",
        ),
        UniqueConstraint(
            "provider",
            "provider_transaction_id",
            name="uq_payment_transactions_provider_transaction",
        ),
        CheckConstraint(
            "amount_minor > 0",
            name="ck_payment_transactions_amount_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    reference: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    provider_transaction_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    plan_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    amount_minor: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
