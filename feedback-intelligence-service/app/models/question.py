from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Index, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    asker_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_questions_owner_category", "owner_user_id", "category"),
    )
