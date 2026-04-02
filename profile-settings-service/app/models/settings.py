from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)

    output_mode: Mapped[str] = mapped_column(String(20), default="video")
    response_length: Mapped[str] = mapped_column(String(20), default="medium")
    creativity_level: Mapped[str] = mapped_column(String(20), default="medium")
    notifications_enabled: Mapped[str] = mapped_column(String(5), default="true")

    voice_id: Mapped[Optional[str]] = mapped_column(String(100))
    personality_intensity: Mapped[Optional[str]] = mapped_column(String(20), default="balanced")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
