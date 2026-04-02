from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VoiceTrainingProfile(Base):
    __tablename__ = "voice_training_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True
    )

    # ElevenLabs cloned voice
    elevenlabs_voice_id: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    voice_name: Mapped[Optional[str]] = mapped_column(String(200), default=None)
    cloning_status: Mapped[str] = mapped_column(String(20), default="pending", insert_default="pending")

    # Voice features
    avg_pitch_hz: Mapped[Optional[float]] = mapped_column(Float, default=None)
    speaking_rate_wpm: Mapped[Optional[float]] = mapped_column(Float, default=None)
    tone_profile: Mapped[Optional[str]] = mapped_column(Text, default=None)

    # Language preferences
    primary_language: Mapped[str] = mapped_column(String(10), default="en", insert_default="en")
    preferred_languages: Mapped[Optional[str]] = mapped_column(Text, default=None)

    # Audio samples
    total_samples: Mapped[int] = mapped_column(Integer, default=0, insert_default=0)
    total_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, insert_default=0.0)

    # Provider sync
    voice_service_synced: Mapped[bool] = mapped_column(Boolean, default=False, insert_default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
