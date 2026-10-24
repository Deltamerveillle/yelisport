"""Technical job state, separate from provider facts and human identities."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SMS24JobCheckpoint(Base):
    __tablename__ = "sms24_job_checkpoints"
    __table_args__ = (
        CheckConstraint("length(job_key) > 0", name="ck_sms24_job_key"),
        CheckConstraint(
            "status IN ('idle', 'running', 'completed', 'completed_with_errors')",
            name="ck_sms24_job_status",
        ),
        CheckConstraint("jsonb_typeof(cursor) = 'object'", name="ck_sms24_job_cursor"),
        CheckConstraint("jsonb_typeof(parameters) = 'object'", name="ck_sms24_job_parameters"),
        CheckConstraint("failed_attempts >= 0", name="ck_sms24_job_failed_attempts"),
        CheckConstraint(
            "(status = 'idle' AND reference_date IS NULL AND started_at IS NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'running' AND reference_date IS NOT NULL AND started_at IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(status IN ('completed', 'completed_with_errors') AND reference_date IS NOT NULL "
            "AND started_at IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_sms24_job_lifecycle",
        ),
    )

    job_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="idle")
    reference_date: Mapped[date | None] = mapped_column(Date)
    cursor: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
