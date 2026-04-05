from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class NotificationType(str, Enum):
    NEW_FOLLOWER = "new_follower"
    FOLLOW_REQUEST = "follow_request"
    FOLLOW_ACCEPTED = "follow_accepted"
    FOLLOW_REJECTED = "follow_rejected"

    FAQ_THRESHOLD = "faq_threshold"
    FAQ_TRENDING = "faq_trending"
    VIRAL_SPIKE = "viral_spike"

    AI_PERSONALITY_UPDATED = "ai_personality_updated"
    AI_MEMORY_UPDATED = "ai_memory_updated"
    AI_VOICE_MODEL_UPDATED = "ai_voice_model_updated"
    AI_BEHAVIOR_SHIFT = "ai_behavior_shift_detected"
    AI_TONE_LEARNED = "ai_tone_learned"
    AI_STYLE_UPDATED = "ai_style_updated"


class NotificationCategory(str, Enum):
    SOCIAL = "social"
    FAQ = "faq"
    VIRAL = "viral"
    AI_EVOLUTION = "ai_evolution"
    SYSTEM = "system"


class NotificationPriority(str, Enum):
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"


EVENT_TYPE_MAP: dict[str, tuple[NotificationCategory, NotificationPriority]] = {
    "new_follower": (NotificationCategory.SOCIAL, NotificationPriority.NORMAL),
    "follow_request": (NotificationCategory.SOCIAL, NotificationPriority.NORMAL),
    "follow_accepted": (NotificationCategory.SOCIAL, NotificationPriority.NORMAL),
    "follow_rejected": (NotificationCategory.SOCIAL, NotificationPriority.NORMAL),
    "faq_threshold": (NotificationCategory.FAQ, NotificationPriority.HIGH),
    "faq_trending": (NotificationCategory.FAQ, NotificationPriority.HIGH),
    "viral_spike": (NotificationCategory.VIRAL, NotificationPriority.HIGH),
    "ai_personality_updated": (NotificationCategory.AI_EVOLUTION, NotificationPriority.CRITICAL),
    "ai_memory_updated": (NotificationCategory.AI_EVOLUTION, NotificationPriority.CRITICAL),
    "ai_voice_model_updated": (NotificationCategory.AI_EVOLUTION, NotificationPriority.CRITICAL),
    "ai_behavior_shift_detected": (NotificationCategory.AI_EVOLUTION, NotificationPriority.CRITICAL),
    "ai_tone_learned": (NotificationCategory.AI_EVOLUTION, NotificationPriority.CRITICAL),
    "ai_style_updated": (NotificationCategory.AI_EVOLUTION, NotificationPriority.CRITICAL),
}


class IncomingEvent(BaseModel):
    event_type: str
    user_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[str] = None
    idempotency_key: Optional[str] = None


class NotificationOut(BaseModel):
    id: str
    user_id: str
    type: str
    category: str
    title: str
    message: str
    priority: str
    status: str
    metadata: str
    created_at: str


class NotificationPreferences(BaseModel):
    follow_notifications: bool = True
    faq_notifications: bool = True
    viral_notifications: bool = True
    ai_evolution_notifications: bool = True
    email_enabled: bool = False
    push_enabled: bool = True
