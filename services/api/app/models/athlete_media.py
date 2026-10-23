"""Private athlete-upload metadata. Never expose unmoderated files as public URLs."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AthleteMedia(Base):
    __tablename__ = "athlete_media"
    __table_args__ = (UniqueConstraint("storage_path", name="uq_athlete_media_path"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    storage_path: Mapped[str] = mapped_column(String(320), nullable=False)
    media_type: Mapped[str] = mapped_column(String(10), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(40), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    moderation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
