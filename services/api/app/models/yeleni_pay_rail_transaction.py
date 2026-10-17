"""Provider-neutral external rail identity, separate from SMS commercial terms."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class YeleniPayRailTransaction(Base):
    __tablename__ = "yeleni_pay_rail_transactions"
    __table_args__ = (
        UniqueConstraint("payment_transaction_id", name="uq_yeleni_rail_payment"),
        UniqueConstraint("rail_code", "external_transaction_id", name="uq_yeleni_rail_external"),
        CheckConstraint("rail_code ~ '^[a-z][a-z0-9-]{0,49}$'", name="ck_yeleni_rail_code"),
        CheckConstraint(
            "status IN ('created', 'pending', 'succeeded', 'failed')",
            name="ck_yeleni_rail_status",
        ),
        CheckConstraint(
            "external_transaction_id IS NULL OR length(btrim(external_transaction_id)) > 0",
            name="ck_yeleni_rail_external_nonempty",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    rail_code: Mapped[str] = mapped_column(String(50), nullable=False)
    external_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="created", server_default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
