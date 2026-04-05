from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SocialContent(Base):
    __tablename__ = "social_content"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_content_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hashtags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mentions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    engagement_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    shares_count: Mapped[int] = mapped_column(Integer, default=0)
    content_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    embedded: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("ix_content_user_platform", "user_id", "platform"),
        Index("ix_content_platform_id", "platform_content_id"),
    )
