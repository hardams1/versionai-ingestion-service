from __future__ import annotations

import logging
from typing import Any

from app.models.notification import (
    EVENT_TYPE_MAP,
    NotificationCategory,
    NotificationPriority,
)

logger = logging.getLogger(__name__)

# Human-readable notification templates keyed by event_type
TEMPLATES: dict[str, tuple[str, str]] = {
    "new_follower": (
        "New Follower",
        "@{username} started following you",
    ),
    "follow_request": (
        "Follow Request",
        "@{username} wants to follow you",
    ),
    "follow_accepted": (
        "Request Accepted",
        "@{username} accepted your follow request",
    ),
    "follow_rejected": (
        "Request Declined",
        "Your follow request was declined",
    ),
    "faq_threshold": (
        "FAQ Milestone",
        "Your category '{category}' reached {count:,} questions!",
    ),
    "faq_trending": (
        "Trending Category",
        "Your AI is trending in the '{category}' category",
    ),
    "viral_spike": (
        "Viral Engagement",
        "Spike detected — your AI is seeing high engagement velocity",
    ),
    "ai_personality_updated": (
        "AI Personality Evolved",
        "Your AI personality was updated based on new {source} data",
    ),
    "ai_memory_updated": (
        "AI Memory Expanded",
        "Memory system has incorporated new interaction patterns",
    ),
    "ai_voice_model_updated": (
        "Voice Model Updated",
        "Your voice model was updated successfully",
    ),
    "ai_behavior_shift_detected": (
        "Behavior Pattern Detected",
        "New behavioral pattern detected in your AI responses",
    ),
    "ai_tone_learned": (
        "New Tone Style Learned",
        "AI has learned a new tone style from {platform} interactions",
    ),
    "ai_style_updated": (
        "Communication Style Updated",
        "Your AI now reflects updated communication style from recent chats",
    ),
}


def route_event(
    event_type: str,
    payload: dict[str, Any],
) -> tuple[str, str, NotificationCategory, NotificationPriority]:
    """Map an event to (title, message, category, priority)."""
    cat, priority = EVENT_TYPE_MAP.get(
        event_type,
        (NotificationCategory.SYSTEM, NotificationPriority.NORMAL),
    )

    title_tpl, msg_tpl = TEMPLATES.get(event_type, ("Notification", "You have a new notification"))

    safe_payload = {k: v for k, v in payload.items() if isinstance(v, (str, int, float))}
    safe_payload.setdefault("username", "someone")
    safe_payload.setdefault("category", "General")
    safe_payload.setdefault("count", 0)
    safe_payload.setdefault("source", "social")
    safe_payload.setdefault("platform", "social media")

    try:
        title = title_tpl.format(**safe_payload)
        message = msg_tpl.format(**safe_payload)
    except (KeyError, ValueError):
        title = title_tpl
        message = msg_tpl

    return title, message, cat, priority
