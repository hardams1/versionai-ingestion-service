from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SocialProfile(Base):
    """Social-layer profile stored alongside the auth/profile-settings data."""

    __tablename__ = "social_profiles"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(200))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True)

    is_private: Mapped[bool] = mapped_column(Boolean, default=False, insert_default=False)
    ai_access_level: Mapped[str] = mapped_column(
        String(20), default="public", insert_default="public",
    )

    followers_count: Mapped[int] = mapped_column(Integer, default=0, insert_default=0)
    following_count: Mapped[int] = mapped_column(Integer, default=0, insert_default=0)
    ai_interaction_count: Mapped[int] = mapped_column(Integer, default=0, insert_default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
